"""Flower Server."""
import time
from collections import OrderedDict
from typing import Callable, Dict, Optional, Tuple

import torch
from flwr.common.typing import NDArrays, Scalar
from torch import nn

from heterofl.models import test
from heterofl.utils import save_model

# from torch.utils.data import DataLoader


def gen_evaluate_fn(
    data_loaders,
    device: torch.device,
    model: nn.Module,
) -> Callable[
    [int, NDArrays, Dict[str, Scalar]], Optional[Tuple[float, Dict[str, Scalar]]]
]:
    """Generate the function for centralized evaluation.

    Parameters
    ----------
    trainloader: DataLoader
        The Dataloader that was used for training the main model
    testloader : DataLoader
        The dataloader to test the model with.
    clients_testloader : List[DataLoader]
        The client's test dataloader to test the model with for local results.
    label_split : List[torch.tensor]
        The list of labels that clients were distributed with.
    device : torch.device
        The device to test the model on.

    Returns
    -------
    Callable[ [int, NDArrays, Dict[str, Scalar]],
            Optional[Tuple[float, Dict[str, Scalar]]] ]
        The centralized evaluation function.
    """

    def evaluate(
        server_round: int, parameters_ndarrays: NDArrays, config: Dict[str, Scalar]
    ) -> Optional[Tuple[float, Dict[str, Scalar]]]:
        # pylint: disable=unused-argument
        """Use the entire test set for evaluation."""
        if server_round % 5 != 0 and server_round < 395:
            return 1, {}

        net = model
        params_dict = zip(net.state_dict().keys(), parameters_ndarrays)
        state_dict = OrderedDict({k: torch.Tensor(v) for k, v in params_dict})
        net.load_state_dict(state_dict, strict=True)
        net.to(device)

        if server_round % 100 == 0:
            save_model(net, f"model_after_round_{server_round}.pth")

        print("start of testing")
        start_time = time.time()
        with torch.no_grad():
            net.train(True)
            for images, labels in data_loaders["entire_trainloader"]:
                input_dict = {}
                input_dict["img"] = images.to(device)
                input_dict["label"] = labels.to(device)
                net(input_dict)
        print(f"end of stat, time taken = {time.time() - start_time}")

        local_metrics = {}
        local_metrics["loss"] = 0
        local_metrics["accuracy"] = 0
        for i, clnt_tstldr in enumerate(data_loaders["valloaders"]):
            client_test_res = test(
                net,
                clnt_tstldr,
                data_loaders["label_split"][i].type(torch.int),
                device=device,
            )
            local_metrics["loss"] += client_test_res[0]
            local_metrics["accuracy"] += client_test_res[1]

        global_metrics = {}
        global_metrics["loss"], global_metrics["accuracy"] = test(
            net, data_loaders["testloader"], device=device
        )

        # return statistics
        print(f"global accuracy = {global_metrics['accuracy']}")
        print(f"local_accuracy = {local_metrics['accuracy']}")
        return global_metrics["loss"], {
            "global_accuracy": global_metrics["accuracy"],
            "local_loss": local_metrics["loss"],
            "local_accuracy": local_metrics["accuracy"],
        }

    return evaluate
