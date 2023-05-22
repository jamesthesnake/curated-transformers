from typing import Any, Mapping, Optional, Type, TypeVar
import torch
from torch.nn import Module, Parameter
from torch import Tensor

from ..attention import AttentionMask
from ..bert.embeddings import BertEmbeddings
from ..hf_hub import FromPretrainedHFModel
from ..output import ModelOutput
from .config import AlbertConfig
from .layer_group import AlbertLayerGroup
from ._hf import convert_hf_config, convert_hf_state_dict

# Only provided as typing.Self in Python 3.11+.
Self = TypeVar("Self", bound="AlbertEncoder")


class AlbertEncoder(Module, FromPretrainedHFModel):
    def __init__(
        self,
        config: AlbertConfig,
    ):
        super().__init__()

        self.padding_id = config.padding_id
        self.max_seq_len = config.model_max_length
        self.num_hidden_layers = config.layer.num_hidden_layers
        num_hidden_groups = config.layer.num_hidden_groups

        if self.num_hidden_layers % num_hidden_groups != 0:
            raise ValueError(
                f"The number of hidden layers ({self.num_hidden_layers}) in the "
                "ALBERT encoder must be divisable by number of hidden groups "
                f"({num_hidden_groups})"
            )

        self.embeddings = BertEmbeddings(config.embedding, config.layer)

        # Parameters are shared by groups of layers.
        self.groups = torch.nn.ModuleList(
            [
                AlbertLayerGroup(config.layer, config.attention)
                for _ in range(num_hidden_groups)
            ]
        )

    def _create_attention_mask(self, x: Tensor) -> AttentionMask:
        return AttentionMask(bool_mask=x.ne(self.padding_id))

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Optional[AttentionMask] = None,
        token_type_ids: Optional[Tensor] = None,
    ) -> ModelOutput:
        """
        Shapes:
            input_ids, attention_mask, token_type_ids - (batch, seq_len)
        """
        if attention_mask is None:
            attention_mask = self._create_attention_mask(input_ids)

        embeddings = self.embeddings(input_ids, token_type_ids, None)
        layer_output = embeddings

        layers_per_group = self.num_hidden_layers // len(self.groups)

        layer_outputs = []
        for group in self.groups:
            for _ in range(layers_per_group):
                layer_output = group(layer_output, attention_mask=attention_mask)
                layer_outputs.append(layer_output)

        return ModelOutput(
            embedding_output=embeddings, layer_hidden_states=layer_outputs
        )

    @classmethod
    def convert_hf_state_dict(cls, params: Mapping[str, Parameter]):
        return convert_hf_state_dict(params)

    @classmethod
    def from_hf_config(cls: Type[Self], *, hf_config: Any) -> Self:
        config = convert_hf_config(hf_config)
        return cls(config)