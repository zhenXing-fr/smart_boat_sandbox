import os
import numpy as np
import tensorflow as tf
from tensorflow.keras import Model
from tensorflow.keras.layers import Input, Dense, Lambda
from tensorflow.keras.optimizers import Adam
from typing import Dict, Tuple, List, Any, Optional
import json
import datetime

class PPOBuffer:
    """
    Buffer for storing trajectory data and computing advantages.
    """
    
    def __init__(self, obs_dim: int, act_dim: int, size: int, gamma: float = 0.99, lam: float = 0.95):
        """
        Initialize the PPO buffer.
        
        Args:
            obs_dim: Observation dimension
            act_dim: Action dimension
            size: Buffer size
            gamma: Discount factor
            lam: GAE (Generalized Advantage Estimation) parameter
        """
        self.obs_buf = np.zeros((size, obs_dim), dtype=np.float32)
        self.act_buf = np.zeros((size, act_dim), dtype=np.float32)
        self.adv_buf = np.zeros(size, dtype=np.float32)
        self.rew_buf = np.zeros(size, dtype=np.float32)
        self.ret_buf = np.zeros(size, dtype=np.float32)
        self.val_buf = np.zeros(size, dtype=np.float32)
        self.logp_buf = np.zeros(size, dtype=np.float32)
        self.gamma, self.lam = gamma, lam
        self.ptr, self.path_start_idx, self.max_size = 0, 0, size
        
    def store(self, obs: np.ndarray, act: np.ndarray, rew: float, val: float, logp: float) -> None:
        """
        Store one transition in the buffer.
        
        Args:
            obs: Observation
            act: Action
            rew: Reward
            val: Value (from value function)
            logp: Log probability of action under current policy
        """
        assert self.ptr < self.max_size
        self.obs_buf[self.ptr] = obs
        self.act_buf[self.ptr] = act
        self.rew_buf[self.ptr] = rew
        self.val_buf[self.ptr] = val
        self.logp_buf[self.ptr] = logp
        self.ptr += 1
        
    def finish_path(self, last_val: float = 0) -> None:
        """
        Compute advantage and return when an episode is completed.
        
        Args:
            last_val: Last value estimate (for incomplete trajectories)
        """
        path_slice = slice(self.path_start_idx, self.ptr)
        rews = np.append(self.rew_buf[path_slice], last_val)
        vals = np.append(self.val_buf[path_slice], last_val)
        
        # GAE-Lambda advantage calculation
        deltas = rews[:-1] + self.gamma * vals[1:] - vals[:-1]
        self.adv_buf[path_slice] = self._discount_cumsum(deltas, self.gamma * self.lam)
        
        # Rewards-to-go (targets for value function)
        self.ret_buf[path_slice] = self._discount_cumsum(rews, self.gamma)[:-1]
        
        self.path_start_idx = self.ptr
        
    def get(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Get all data from the buffer and normalize advantages.
        
        Returns:
            Tuple of observations, actions, advantages, returns, log probabilities
        """
        assert self.ptr == self.max_size
        self.ptr, self.path_start_idx = 0, 0
        
        # Normalize advantages
        adv_mean, adv_std = np.mean(self.adv_buf), np.std(self.adv_buf)
        self.adv_buf = (self.adv_buf - adv_mean) / (adv_std + 1e-8)
        
        return (
            self.obs_buf,
            self.act_buf,
            self.adv_buf,
            self.ret_buf,
            self.logp_buf
        )
    
    def _discount_cumsum(self, x: np.ndarray, discount: float) -> np.ndarray:
        """
        Calculate discounted cumulative sum.
        
        Args:
            x: Input array
            discount: Discount factor
            
        Returns:
            Discounted cumulative sum
        """
        return np.array([np.sum([discount**i * x[i + j] for i in range(len(x) - j)]) for j in range(len(x))])


class PPOAgent:
    """
    Proximal Policy Optimization agent for maritime navigation.
    """
    
    def __init__(self, obs_dim: int, act_dim: int, config: Dict[str, Any] = None):
        """
        Initialize the PPO agent.
        
        Args:
            obs_dim: Observation dimension
            act_dim: Action dimension
            config: Optional configuration parameters
        """
        # Default configuration
        self.config = {
            "pi_lr": 3e-4,
            "vf_lr": 1e-3,
            "clip_ratio": 0.2,
            "target_kl": 0.01,
            "train_pi_iters": 80,
            "train_v_iters": 80,
            "gamma": 0.99,
            "lam": 0.97,
            "batch_size": 64,
            "hidden_sizes": [64, 64],
            "mse_criterion": tf.keras.losses.MeanSquaredError(),
        }
        
        # Update with provided configuration
        if config:
            self.config.update(config)
        
        # Create actor and critic models
        self.pi_model = self._build_policy_model(obs_dim, act_dim)
        self.v_model = self._build_value_model(obs_dim)
        
        # Set up optimizers
        self.pi_optimizer = Adam(learning_rate=self.config["pi_lr"])
        self.v_optimizer = Adam(learning_rate=self.config["vf_lr"])
        
        # Training metrics
        self.metrics = {
            "policy_loss": [],
            "value_loss": [],
            "kl": [],
            "entropy": [],
            "episode_returns": [],
            "episode_lengths": []
        }
        
        # Action bounds for scaling
        self.act_scale = np.array([2.0, 15.0])  # Matches environment action space
        
    def _build_policy_model(self, obs_dim: int, act_dim: int) -> Model:
        """
        Build the policy (actor) network.
        
        Args:
            obs_dim: Observation dimension
            act_dim: Action dimension
            
        Returns:
            TensorFlow policy model
        """
        inputs = Input(shape=(obs_dim,))
        x = inputs
        
        # Hidden layers
        for size in self.config["hidden_sizes"]:
            x = Dense(size, activation='tanh')(x)
        
        # Output layers for mean and log standard deviation
        mu = Dense(act_dim, activation='tanh')(x)
        log_std = Dense(act_dim, activation='linear')(x)
        
        # Scale actions to environment range
        mu = Lambda(lambda x: x * self.act_scale)(mu)
        
        # Create model
        model = Model(inputs=inputs, outputs=[mu, log_std])
        
        return model
    
    def _build_value_model(self, obs_dim: int) -> Model:
        """
        Build the value function (critic) network.
        
        Args:
            obs_dim: Observation dimension
            
        Returns:
            TensorFlow value model
        """
        inputs = Input(shape=(obs_dim,))
        x = inputs
        
        # Hidden layers
        for size in self.config["hidden_sizes"]:
            x = Dense(size, activation='tanh')(x)
        
        # Output layer
        outputs = Dense(1, activation='linear')(x)
        
        # Create model
        model = Model(inputs=inputs, outputs=outputs)
        
        return model
    
    def select_action(self, obs: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """
        Select an action given an observation.
        
        Args:
            obs: Observation
            
        Returns:
            Tuple of selected action, log probability, and value estimate
        """
        obs = obs.reshape(1, -1).astype(np.float32)
        
        # Get action distribution parameters
        mu, log_std = self.pi_model(obs)
        std = tf.exp(log_std)
        
        # Sample from the distribution
        noise = tf.random.normal(shape=mu.shape)
        action = mu + noise * std
        
        # Calculate log probability
        logp = self._gaussian_likelihood(action, mu, log_std)
        
        # Get value estimate
        v = self.v_model(obs)[0, 0]
        
        return action[0].numpy(), logp.numpy()[0], v.numpy()
    
    def _gaussian_likelihood(self, x: tf.Tensor, mu: tf.Tensor, log_std: tf.Tensor) -> tf.Tensor:
        """
        Calculate log likelihood of a Gaussian distribution.
        
        Args:
            x: Value
            mu: Mean
            log_std: Log standard deviation
            
        Returns:
            Log probability
        """
        pre_sum = -0.5 * (
            tf.reduce_sum(((x - mu) / (tf.exp(log_std) + 1e-8))**2 + 2 * log_std, axis=1)
            + np.log(2 * np.pi) * tf.cast(tf.shape(x)[1], tf.float32)
        )
        return pre_sum
    
    def update(self, buffer: PPOBuffer) -> Dict[str, float]:
        """
        Update policy and value function using data from buffer.
        
        Args:
            buffer: Buffer containing trajectory data
            
        Returns:
            Dictionary of training metrics
        """
        # Get buffer data
        obs_buf, act_buf, adv_buf, ret_buf, logp_buf = buffer.get()
        
        # Train policy with multiple steps of gradient descent
        for i in range(self.config["train_pi_iters"]):
            pi_loss, kl, entropy = self._update_policy(obs_buf, act_buf, adv_buf, logp_buf)
            
            # Early stopping based on KL divergence
            if kl > 1.5 * self.config["target_kl"]:
                print(f"Early stopping at policy iteration {i} due to reaching max KL divergence.")
                break
        
        # Train value function with multiple steps of gradient descent
        for i in range(self.config["train_v_iters"]):
            v_loss = self._update_value(obs_buf, ret_buf)
        
        # Save metrics
        self.metrics["policy_loss"].append(pi_loss)
        self.metrics["value_loss"].append(v_loss)
        self.metrics["kl"].append(kl)
        self.metrics["entropy"].append(entropy)
        
        return {
            "PolicyLoss": float(pi_loss),
            "ValueLoss": float(v_loss),
            "KL": float(kl),
            "Entropy": float(entropy)
        }
    
    @tf.function
    def _update_policy(self, obs: np.ndarray, act: np.ndarray, adv: np.ndarray, 
                      old_logp: np.ndarray) -> Tuple[tf.Tensor, tf.Tensor, tf.Tensor]:
        """
        Update policy network.
        
        Args:
            obs: Observations
            act: Actions
            adv: Advantages
            old_logp: Old log probabilities
            
        Returns:
            Loss, KL divergence, and entropy
        """
        with tf.GradientTape() as tape:
            # Get current policy distribution
            mu, log_std = self.pi_model(obs)
            std = tf.exp(log_std)
            
            # Calculate log probability of actions
            logp = self._gaussian_likelihood(act, mu, log_std)
            
            # Calculate ratio and clipped objective
            ratio = tf.exp(logp - old_logp)
            clip_ratio = self.config["clip_ratio"]
            min_adv = tf.where(adv > 0, 
                               (1 + clip_ratio) * adv, 
                               (1 - clip_ratio) * adv)
            
            # PPO policy loss
            pi_loss = -tf.reduce_mean(tf.minimum(ratio * adv, min_adv))
            
            # Calculate KL divergence and entropy for monitoring
            approx_kl = tf.reduce_mean(old_logp - logp)
            entropy = tf.reduce_mean(tf.reduce_sum(0.5 * (tf.math.log(2 * np.pi) + 1 + 2 * log_std), axis=1))
        
        # Calculate gradients and update policy network
        pi_gradients = tape.gradient(pi_loss, self.pi_model.trainable_variables)
        self.pi_optimizer.apply_gradients(zip(pi_gradients, self.pi_model.trainable_variables))
        
        return pi_loss, approx_kl, entropy
    
    @tf.function
    def _update_value(self, obs: np.ndarray, ret: np.ndarray) -> tf.Tensor:
        """
        Update value network.
        
        Args:
            obs: Observations
            ret: Returns (targets)
            
        Returns:
            Value loss
        """
        with tf.GradientTape() as tape:
            # Get current value estimates
            v = self.v_model(obs)[:, 0]
            
            # Value loss
            v_loss = self.config["mse_criterion"](v, ret)
        
        # Calculate gradients and update value network
        v_gradients = tape.gradient(v_loss, self.v_model.trainable_variables)
        self.v_optimizer.apply_gradients(zip(v_gradients, self.v_model.trainable_variables))
        
        return v_loss
    
    def save(self, filepath: str, iteration: int) -> None:
        """
        Save model weights and metrics.
        
        Args:
            filepath: Directory to save models
            iteration: Current iteration number
        """
        os.makedirs(filepath, exist_ok=True)
        
        # Save model weights
        self.pi_model.save_weights(f"{filepath}/pi_model_{iteration}.h5")
        self.v_model.save_weights(f"{filepath}/v_model_{iteration}.h5")
        
        # Save metrics
        with open(f"{filepath}/metrics_{iteration}.json", 'w') as f:
            json.dump({
                "policy_loss": [float(x) for x in self.metrics["policy_loss"]],
                "value_loss": [float(x) for x in self.metrics["value_loss"]],
                "kl": [float(x) for x in self.metrics["kl"]],
                "entropy": [float(x) for x in self.metrics["entropy"]],
                "episode_returns": self.metrics["episode_returns"],
                "episode_lengths": self.metrics["episode_lengths"],
                "timestamp": datetime.datetime.now().isoformat(),
                "iteration": iteration
            }, f, indent=2)
        
        # Save latest symlink
        if os.path.exists(f"{filepath}/pi_model_latest.h5"):
            os.remove(f"{filepath}/pi_model_latest.h5")
        if os.path.exists(f"{filepath}/v_model_latest.h5"):
            os.remove(f"{filepath}/v_model_latest.h5")
        
        os.symlink(f"pi_model_{iteration}.h5", f"{filepath}/pi_model_latest.h5")
        os.symlink(f"v_model_{iteration}.h5", f"{filepath}/v_model_latest.h5")
    
    def load(self, filepath: str, iteration: Optional[str] = "latest") -> None:
        """
        Load model weights.
        
        Args:
            filepath: Directory to load models from
            iteration: Iteration to load, or "latest"
        """
        if iteration == "latest":
            pi_file = f"{filepath}/pi_model_latest.h5"
            v_file = f"{filepath}/v_model_latest.h5"
        else:
            pi_file = f"{filepath}/pi_model_{iteration}.h5"
            v_file = f"{filepath}/v_model_{iteration}.h5"
        
        self.pi_model.load_weights(pi_file)
        self.v_model.load_weights(v_file)
        
        print(f"Loaded model weights from {filepath}, iteration {iteration}") 