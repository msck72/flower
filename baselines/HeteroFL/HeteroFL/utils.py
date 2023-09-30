"""Contains utility functions."""
from pathlib import Path

import numpy as np
import torch
from hydra.core.hydra_config import HydraConfig


def preprocess_input(cfg_model, cfg_data):
    """Preprocess the input to get input shape, other derivables.

    Parameters
    ----------
    cfg_model : DictConfig
        Retrieve model-related information from the base.yaml configuration in Hydra.
    cfg_data : DictConfig
        Retrieve data-related information required to construct the model.

    Returns
    -------
    Dict
        Dictionary contained derived information from config.
    """
    model_config = {}
    # if cfg_model.model_name == "conv":
    #     model_config["model_name"] =
    # elif for others...
    model_config["model"] = cfg_model.model_name
    if cfg_data.dataset_name == "MNIST":
        model_config["data_shape"] = [1, 28, 28]
        model_config["classes_size"] = 10
    elif cfg_data.dataset_name == "CIFAR10":
        model_config["data_shape"] = [3, 32, 32]
        model_config["classes_size"] = 10

    model_config["hidden_layers"] = cfg_model.hidden_layers
    model_config["norm"] = cfg_model.norm

    return model_config


def make_optimizer(optimizer_name, parameters, lr, weight_decay, momentum):
    """Make the optimizer with given config.

    Parameters
    ----------
    optimizer_name : str
        Name of the optimizer.
    parameters : Dict
        Parameters of the model.
    lr: float
        Learning rate of the optimizer.
    weight_decay: float
        weight_decay of the optimizer.

    Returns
    -------
    torch.optim.Optimizer
        Optimizer.
    """
    if optimizer_name == "SGD":
        return torch.optim.SGD(
            parameters, lr=lr, momentum=momentum, weight_decay=weight_decay
        )


def make_scheduler(scheduler_name, optimizer, milestones):
    """Make the scheduler with given config.

    Parameters
    ----------
    scheduler_name : str
        Name of the scheduler.
    optimizer : torch.optim.Optimizer
        Parameters of the model.
    milestones: List[int]
        List of epoch indices. Must be increasing.

    Returns
    -------
    torch.optim.lr_scheduler.Scheduler
        scheduler.
    """
    if scheduler_name == "MultiStepLR":
        return torch.optim.lr_scheduler.MultiStepLR(optimizer, milestones=milestones)


def get_global_model_rate(model_mode):
    """Give the global model rate from string(cfg.control.model_mode) .

    Parameters
    ----------
    model_mode : str
        Contains the division of computational complexties among clients.

    Returns
    -------
    str
        global model computational complexity.
    """
    model_mode = "" + model_mode
    model_mode = model_mode.split("-")[0][0]
    return model_mode


class Model_rate_manager:
    """Control the model rate of clients in case of simulation."""

    def __init__(self, model_split_mode, model_split_rate, model_mode):
        self.model_split_mode = model_split_mode
        self.model_split_rate = model_split_rate
        self.model_mode = model_mode
        self.model_mode = self.model_mode.split("-")

    def create_model_rate_mapping(self, num_users):
        """Change the client to model rate mapping accordingly."""
        client_model_rate = []

        if self.model_split_mode == "fix":
            mode_rate, proportion = [], []
            for m in self.model_mode:
                mode_rate.append(self.model_split_rate[m[0]])
                proportion.append(int(m[1:]))
            num_users_proportion = num_users // sum(proportion)
            for i in range(len(mode_rate)):
                client_model_rate += np.repeat(
                    mode_rate[i], num_users_proportion * proportion[i]
                ).tolist()
            client_model_rate = client_model_rate + [
                client_model_rate[-1] for _ in range(num_users - len(client_model_rate))
            ]
            return client_model_rate

        elif self.model_split_mode == "dynamic":
            mode_rate, proportion = [], []

            for m in self.model_mode:
                mode_rate.append(self.model_split_rate[m[0]])
                proportion.append(int(m[1:]))

            proportion = (np.array(proportion) / sum(proportion)).tolist()

            rate_idx = torch.multinomial(
                torch.tensor(proportion), num_samples=num_users, replacement=True
            ).tolist()
            client_model_rate = np.array(mode_rate)[rate_idx]

            return client_model_rate

        else:
            return None


def save_model(model, path):
    """To save the model in the given path."""
    # print('in save model')
    current_path = HydraConfig.get().runtime.output_dir
    model_save_path = Path(current_path) / path
    torch.save(model.state_dict(), model_save_path)