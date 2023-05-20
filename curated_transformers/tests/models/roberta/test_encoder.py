import pytest

from curated_transformers._compat import has_hf_transformers
from curated_transformers.models.roberta.encoder import RobertaEncoder

from ...conftest import TORCH_DEVICES
from ..util import assert_encoder_output_equals_hf


@pytest.mark.skipif(not has_hf_transformers, reason="requires huggingface transformers")
@pytest.mark.parametrize("torch_device", TORCH_DEVICES)
def test_encoder(torch_device):
    assert_encoder_output_equals_hf(
        RobertaEncoder, "explosion-testing/roberta-test", torch_device
    )
