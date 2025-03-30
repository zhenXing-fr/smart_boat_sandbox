#!/usr/bin/env python3
"""
Train a reinforcement learning model for maritime route optimization.
This script uses PPO to train an agent to navigate safely and efficiently in the maritime environment.
"""

import os
import sys
import argparse
import numpy as np
import json
import time
import datetime
from typing import Dict, List, Any, Tuple, Optional

import tensorflow as tf
from tensorflow.keras.utils import plot_model

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.maritime_environment import MaritimeEnvironment
from models.rl_agent import PPOAgent, PPOBuffer


def train(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Train the PPO agent in the maritime environment.
    
    Args:
        config: Configuration dictionary with training parameters
        
    Returns:
        Dictionary with training results
    """
    print(f"Starting RL training with config: {config}")
    
    # Set up output directories
    output_dir = config.get("output_dir", "models/rl")
    os.makedirs(output_dir, exist_ok=True)
    
    trajectories_dir = os.path.join(output_dir, "trajectories")
    os.makedirs(trajectories_dir, exist_ok=True)
    
    # Save configuration
    with open(os.path.join(output_dir, "config.json"), 'w') as f:
        json.dump(config, f, indent=2)
    
    # Create environment
    env_config = config.get("env_config", {})
    env = MaritimeEnvironment(env_config)
    
    # Create agent
    obs_dim = env.observation_space.shape[0]
    act_dim = env.action_space.shape[0]
    agent_config = config.get("agent_config", {})
    agent = PPOAgent(obs_dim, act_dim, agent_config)
    
    # Plot model architecture if enabled
    if config.get("plot_model", False):
        try:
            plot_model(agent.pi_model, to_file=os.path.join(output_dir, "policy_model.png"), show_shapes=True)
            plot_model(agent.v_model, to_file=os.path.join(output_dir, "value_model.png"), show_shapes=True)
            print(f"Model architecture diagrams saved to {output_dir}")
        except Exception as e:
            print(f"Could not plot model: {e}")
    
    # Training parameters
    epochs = config.get("epochs", 100)
    steps_per_epoch = config.get("steps_per_epoch", 1000)
    max_ep_len = config.get("max_ep_len", 500)
    save_freq = config.get("save_freq", 10)
    num_vessels = config.get("num_vessels", 3)
    
    # Initialize data collection
    all_metrics = []
    vessel_stats = {f"vessel_{i+1}": {"success_rate": [], "avg_reward": [], "avg_distance": []} 
                   for i in range(num_vessels)}
    
    # Training loop
    for epoch in range(epochs):
        start_time = time.time()
        print(f"\nEpoch {epoch + 1}/{epochs}")
        
        # Create buffer for collecting trajectories
        buffer = PPOBuffer(obs_dim, act_dim, steps_per_epoch, 
                           gamma=agent.config["gamma"], 
                           lam=agent.config["lam"])
        
        # Collect trajectories for each vessel
        for vessel_idx in range(num_vessels):
            vessel_id = f"vessel_{vessel_idx + 1}"
            print(f"Collecting trajectory for {vessel_id}")
            
            # Track episode statistics
            ep_returns = []
            ep_lengths = []
            successes = 0
            distances = []
            
            # Collect steps for this vessel until buffer is full
            steps_collected = 0
            while steps_collected < steps_per_epoch // num_vessels:
                # Reset environment and episode variables
                obs = env.reset(vessel_id=vessel_id)
                ep_return = 0
                ep_length = 0
                
                # Episode loop
                for step in range(max_ep_len):
                    # Select action
                    action, logp, value = agent.select_action(obs)
                    
                    # Take action in environment
                    next_obs, reward, done, info = env.step(action)
                    
                    # Store transition in buffer
                    buffer.store(obs, action, reward, value, logp)
                    
                    # Update episode statistics
                    obs = next_obs
                    ep_return += reward
                    ep_length += 1
                    
                    # Count steps collected
                    steps_collected += 1
                    
                    # Check if episode is finished or buffer is full
                    timeout = ep_length == max_ep_len
                    terminal = done or timeout
                    epoch_ended = steps_collected == steps_per_epoch // num_vessels
                    
                    if terminal or epoch_ended:
                        # If trajectory didn't reach terminal state, bootstrap value target
                        if epoch_ended and not terminal:
                            _, _, last_val = agent.select_action(obs)
                        else:
                            last_val = 0
                        
                        # Finish path and record stats
                        buffer.finish_path(last_val)
                        
                        if terminal:
                            # Only save completed trajectories
                            ep_returns.append(ep_return)
                            ep_lengths.append(ep_length)
                            
                            # Record success and final distance
                            if info.get("termination_reason") == "destination_reached":
                                successes += 1
                            
                            distances.append(info.get("distance_to_destination", float('inf')))
                            
                            # Save trajectory for visualization
                            if epoch % save_freq == 0:
                                trajectory_file = os.path.join(
                                    trajectories_dir, 
                                    f"{vessel_id}_trajectory_epoch_{epoch + 1}_episode_{len(ep_returns)}.json"
                                )
                                env.save_trajectory(trajectory_file)
                            
                        if epoch_ended:
                            break
            
            # Update vessel statistics
            if ep_returns:  # Only update if we have complete episodes
                avg_return = sum(ep_returns) / len(ep_returns)
                avg_length = sum(ep_lengths) / len(ep_lengths)
                success_rate = successes / len(ep_returns) if ep_returns else 0
                avg_distance = sum(distances) / len(distances) if distances else float('inf')
                
                vessel_stats[vessel_id]["success_rate"].append(success_rate)
                vessel_stats[vessel_id]["avg_reward"].append(avg_return)
                vessel_stats[vessel_id]["avg_distance"].append(avg_distance)
                
                print(f"{vessel_id} - Avg Return: {avg_return:.2f}, Success Rate: {success_rate:.2f}, "
                      f"Avg Episode Length: {avg_length:.1f}")
                
                # Store in agent's metrics for tracking
                agent.metrics["episode_returns"].extend(ep_returns)
                agent.metrics["episode_lengths"].extend(ep_lengths)
        
        # Update policy using all collected data
        print("Updating policy...")
        update_metrics = agent.update(buffer)
        
        # Record combined metrics
        combined_metrics = {
            "epoch": epoch + 1,
            "time": time.time() - start_time,
            **update_metrics,
            "vessel_stats": {
                vessel_id: {
                    "success_rate": stats["success_rate"][-1] if stats["success_rate"] else 0,
                    "avg_reward": stats["avg_reward"][-1] if stats["avg_reward"] else 0,
                    "avg_distance": stats["avg_distance"][-1] if stats["avg_distance"] else float('inf')
                } for vessel_id, stats in vessel_stats.items()
            }
        }
        all_metrics.append(combined_metrics)
        
        print(f"Epoch {epoch + 1} completed in {combined_metrics['time']:.2f}s")
        print(f"Policy Loss: {combined_metrics['PolicyLoss']:.6f}, Value Loss: {combined_metrics['ValueLoss']:.6f}, "
              f"KL: {combined_metrics['KL']:.6f}, Entropy: {combined_metrics['Entropy']:.6f}")
        
        # Save model periodically
        if (epoch + 1) % save_freq == 0 or (epoch + 1) == epochs:
            print(f"Saving model at epoch {epoch + 1}")
            agent.save(output_dir, epoch + 1)
            
            # Save all metrics
            with open(os.path.join(output_dir, "training_metrics.json"), 'w') as f:
                json.dump(all_metrics, f, indent=2)
            
            # Save vessel stats
            with open(os.path.join(output_dir, "vessel_stats.json"), 'w') as f:
                json.dump(vessel_stats, f, indent=2)
    
    # Final save of metrics and models
    print("Training completed. Final model and metrics saved.")
    
    # Return training results
    return {
        "output_dir": output_dir,
        "epochs_completed": epochs,
        "final_metrics": all_metrics[-1] if all_metrics else None,
        "vessel_stats": vessel_stats
    }


def generate_monte_carlo_visualizations(model_dir: str, num_iterations: int = 10) -> Dict[str, Any]:
    """
    Generate Monte Carlo path visualizations by running multiple episodes with the trained model.
    
    Args:
        model_dir: Directory containing the trained model
        num_iterations: Number of Monte Carlo iterations per vessel
        
    Returns:
        Dictionary with visualization data
    """
    print(f"Generating {num_iterations} Monte Carlo visualizations")
    
    # Load configuration
    with open(os.path.join(model_dir, "config.json"), 'r') as f:
        config = json.load(f)
    
    # Create environment
    env_config = config.get("env_config", {})
    env = MaritimeEnvironment(env_config)
    
    # Create agent
    obs_dim = env.observation_space.shape[0]
    act_dim = env.action_space.shape[0]
    agent_config = config.get("agent_config", {})
    agent = PPOAgent(obs_dim, act_dim, agent_config)
    
    # Load latest model
    agent.load(model_dir)
    
    # Output directory for visualization data
    viz_dir = os.path.join(model_dir, "monte_carlo")
    os.makedirs(viz_dir, exist_ok=True)
    
    # Generate visualizations for each vessel
    visualization_data = {}
    
    for vessel_idx in range(config.get("num_vessels", 3)):
        vessel_id = f"vessel_{vessel_idx + 1}"
        viz_vessel_dir = os.path.join(viz_dir, vessel_id)
        os.makedirs(viz_vessel_dir, exist_ok=True)
        
        # Store all trajectories for this vessel
        vessel_trajectories = []
        
        # Run multiple episodes
        for i in range(num_iterations):
            print(f"Generating trajectory {i + 1}/{num_iterations} for {vessel_id}")
            
            # Reset environment
            obs = env.reset(vessel_id=vessel_id)
            done = False
            
            # Episode loop
            while not done:
                # Select deterministic action (no exploration)
                action, _, _ = agent.select_action(obs)
                
                # Take action in environment
                obs, _, done, _ = env.step(action)
            
            # Save trajectory
            trajectory_file = os.path.join(viz_vessel_dir, f"mc_iteration_{i + 1}.json")
            env.save_trajectory(trajectory_file)
            
            # Store trajectory data
            vessel_trajectories.append({
                "iteration": i + 1,
                "trajectory_file": trajectory_file,
                "steps": env.steps,
                "destination_reached": any(step.get("reward", 0) > 50 for step in env.trajectory),
                "hazard_hit": any("hit_hazard" in step.get("info", {}).get("termination_reason", "") 
                                 for step in env.trajectory),
                "fuel_depleted": any("out_of_fuel" in step.get("info", {}).get("termination_reason", "") 
                                    for step in env.trajectory)
            })
        
        # Create summary file for vessel
        with open(os.path.join(viz_vessel_dir, "summary.json"), 'w') as f:
            json.dump({
                "vessel_id": vessel_id,
                "num_iterations": num_iterations,
                "success_rate": sum(1 for t in vessel_trajectories if t["destination_reached"]) / num_iterations,
                "avg_steps": sum(t["steps"] for t in vessel_trajectories) / num_iterations,
                "trajectories": vessel_trajectories
            }, f, indent=2)
        
        # Store in overall visualization data
        visualization_data[vessel_id] = vessel_trajectories
    
    # Create overall summary
    summary = {
        "model_dir": model_dir,
        "generation_time": datetime.datetime.now().isoformat(),
        "num_iterations": num_iterations,
        "vessels": list(visualization_data.keys()),
        "aggregate_success_rate": sum(
            sum(1 for t in trajectories if t["destination_reached"]) 
            for trajectories in visualization_data.values()
        ) / (len(visualization_data) * num_iterations)
    }
    
    with open(os.path.join(viz_dir, "mc_summary.json"), 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Monte Carlo visualizations generated and saved to {viz_dir}")
    return summary


def main() -> None:
    """Main function to parse arguments and run training or visualization."""
    parser = argparse.ArgumentParser(description="Train RL model for maritime route optimization")
    parser.add_argument("--config", type=str, default="config/rl_config.json", 
                        help="Path to configuration file")
    parser.add_argument("--output", type=str, default="models/rl", 
                        help="Output directory for models and visualizations")
    parser.add_argument("--visualize-only", action="store_true", 
                        help="Only generate visualizations, don't train")
    parser.add_argument("--mc-iterations", type=int, default=10, 
                        help="Number of Monte Carlo iterations for visualization")
    args = parser.parse_args()
    
    # Load configuration
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
    else:
        print(f"Configuration file {args.config} not found, using defaults")
        config = {}
    
    # Set output directory
    config["output_dir"] = args.output
    
    # Run training or visualization
    if args.visualize_only:
        generate_monte_carlo_visualizations(args.output, args.mc_iterations)
    else:
        # Run training
        train_results = train(config)
        
        # Generate visualizations after training
        generate_monte_carlo_visualizations(args.output, args.mc_iterations)


if __name__ == "__main__":
    main() 