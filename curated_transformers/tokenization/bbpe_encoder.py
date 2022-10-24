from typing import List, Optional

from cutlery import ByteBPEProcessor
from spacy.tokens import Doc
import srsly
from thinc.api import Model, Ragged, deserialize_attr, serialize_attr

from .._compat import has_hf_transformers, transformers
from ..util import registry


@serialize_attr.register(ByteBPEProcessor)
def serialize_byte_bpe_processor(_, value: ByteBPEProcessor, name: str, model) -> bytes:
    data = {"merges": value.merges, "vocab": value.vocab}
    return srsly.msgpack_dumps(data)


@deserialize_attr.register(ByteBPEProcessor)
def deserialize_byte_bpe_processor(
    _, value: bytes, name: str, model
) -> ByteBPEProcessor:
    data = srsly.msgpack_loads(value)
    return ByteBPEProcessor(data["vocab"], data["merges"])


def build_byte_bpe_encoder() -> Model[List[Doc], List[Ragged]]:
    return Model(
        "byte_bpe_encoder",
        forward=byte_bpe_encoder_forward,
        attrs={
            "byte_bpe_processor": ByteBPEProcessor({}, []),
            "unk_piece": "<unk>",
            "bos_piece": "<s>",
            "eos_piece": "</s>",
        },
    )


def byte_bpe_encoder_forward(model: Model, X: List[Doc], is_train: bool):
    bbp: ByteBPEProcessor = model.attrs["byte_bpe_processor"]
    bos_piece: str = model.attrs["bos_piece"]
    eos_piece: str = model.attrs["eos_piece"]
    unk_piece: str = model.attrs["unk_piece"]
    bos_id = bbp.piece_id(bos_piece)
    if bos_id is None:
        raise ValueError("Vocabulary does not have BOS piece")
    eos_id = bbp.piece_id(eos_piece)
    if eos_id is None:
        raise ValueError("Vocabulary does not have EOS piece")
    unk_id = bbp.piece_id(unk_piece)
    if unk_id is None:
        raise ValueError("Vocabulary does not have UNK piece")

    pieces = []
    for doc in X:
        # TODO: check whether as single bos/eos per doc is what we want.
        #   The issue is that we probably do not have sentence
        #   boundaries yet, since they are predicted by a pipe.
        doc_pieces = [bos_id]
        lens = [1]

        for idx, token in enumerate(doc):
            # GPT-2/RoBERTa tokenization preserves preceding space character.
            if idx > 0:
                text = doc[idx - 1].whitespace_ + token.text
            else:
                text = token.text

            piece_ids = bbp.encode_as_ids(text)

            doc_pieces.extend(piece_ids)
            lens.append(len(piece_ids))

        doc_pieces.append(eos_id)
        lens.append(1)
        pieces.append(
            Ragged(
                model.ops.asarray1i(doc_pieces),
                model.ops.asarray1i(lens),
            )
        )

    return pieces, lambda dY: []