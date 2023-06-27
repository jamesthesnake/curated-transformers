import pytest
import torch

from curated_transformers._compat import has_hf_transformers, transformers
from curated_transformers.models.attention import AttentionMask
from curated_transformers.models.refined_web_model.decoder import RefinedWebModelDecoder
from curated_transformers.tests.util import torch_assertclose

from ...conftest import TORCH_DEVICES

VOCAB_SIZE = 1024

# We do not have tests to check caching/positions against upstream, there
# are two issues with the upstream model:
#
# 1. It uses the torch scaled dot-product attention, but that has a bug
#    in generating causal masks:
#
#    https://github.com/pytorch/pytorch/issues/103082
#
# 2. When using a cache, the upstream implementation does not take into
#    account that we need to index by position into the rotary embeddings.
#
# We test caching instead by comparing output of the model with caching
# against output without caching.


@pytest.mark.skipif(not has_hf_transformers, reason="requires huggingface transformers")
@pytest.mark.parametrize("torch_device", TORCH_DEVICES)
def test_decoder(torch_device):
    hf_model = transformers.AutoModel.from_pretrained(
        "explosion-testing/refined-web-model-test",
        # Safe because it is under our control.
        trust_remote_code=True,
        # Avoid warnings about trusting remote code without a revision.
        revision="235f4b64c489e33ae7e40163ab1f266bbe355651",
    )
    hf_model.to(torch_device)
    hf_model.eval()

    model = RefinedWebModelDecoder.from_hf_hub(
        "explosion-testing/refined-web-model-test", device=torch_device
    )
    model.eval()

    torch.manual_seed(0)
    X = torch.randint(0, hf_model.config.vocab_size, (2, 10), device=torch_device)

    with torch.no_grad():
        Y = model(X).last_hidden_layer_states
        Y_hf = hf_model(X).last_hidden_state

    torch_assertclose(Y, Y_hf)


@pytest.mark.skipif(not has_hf_transformers, reason="requires huggingface transformers")
@pytest.mark.parametrize("torch_device", TORCH_DEVICES)
def test_decoder_with_cache(torch_device):
    model = RefinedWebModelDecoder.from_hf_hub(
        "explosion-testing/refined-web-model-test", device=torch_device
    )
    model.eval()

    torch.manual_seed(0)
    X = torch.randint(0, VOCAB_SIZE, (2, 10), device=torch_device)
    X_rest = torch.randint(0, VOCAB_SIZE, (2, 10), device=torch_device)

    with torch.no_grad():
        Y = model(X, store_cache=True)
        Y = model(X_rest, cache=Y.cache).last_hidden_layer_states
        Y_no_cache = model(torch.cat([X, X_rest], dim=1)).last_hidden_layer_states

    torch_assertclose(Y, Y_no_cache[:, 10:, :])