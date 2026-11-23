# The ComfyUI setup

Everything needed to render a portrait exactly as the ones in this repository were
rendered. The machinery that *drives* it — the queue, the multi-machine scheduler,
the metadata stamper — is private infrastructure and is not here, because none of
it is needed to reproduce a face. A seed, a prompt and this graph are.

## The model

**RealVisXL V5.0 Lightning**, `RealVisXL_V5.0_Lightning_fp16.safetensors`, a single
self-contained SDXL checkpoint of about 6.5 GB with the UNet, both text encoders
and the VAE baked in.

It was chosen by measurement on an Apple M4 with 16 GB of *unified* memory —
shared between CPU and GPU, no separate VRAM — against the obvious alternatives:

| Model | Config | Time | Fits in 16 GB? |
|---|---|---|---|
| Z-Image-Turbo | 4 steps, 512² | 178–217 s warm | No — ~19 GB combined, swaps |
| Flux1-schnell-fp8 | 4 steps, 512² | fails | No — fp8 is unsupported on Apple's MPS backend, and the bf16 workaround wants ~21 GB against MPS's own ~20 GB ceiling |
| **RealVisXL V5.0 Lightning** | **6 steps, 1024²** | **54 s warm** | **Yes — ~6.5 GB, no swap** |

Two traps worth repeating, both of which cost real time to find:

- **Do not pass `--novram` or `--lowvram`.** They help models that do not fit. On
  one that does, they force a CPU-offload attention path measured about **35×
  slower**. Launch ComfyUI plainly.
- **fp8 checkpoints do not run on Apple MPS at all** — not only the `--fp8_e4m3fn-*`
  casting flags, but any `.safetensors` whose weights are already stored in fp8.

On an NVIDIA or Intel GPU with more memory, none of this applies; the graph is
ordinary SDXL and will run anywhere ComfyUI runs.

## The graph

`workflow_api.json` is ComfyUI's API-format graph, seven nodes:

```
CheckpointLoaderSimple → CLIPTextEncode ×2 (positive, negative)
                       → KSampler → VAEDecode → SaveImage
                         EmptyLatentImage ↗
```

Sampling is **6 steps, cfg 2.0, `dpmpp_sde` with the `karras` scheduler, denoise
1.0, 1024×1024**. Lightning checkpoints are distilled for very low step counts;
raising steps or cfg towards ordinary SDXL values makes the output worse, not
better.

Three inputs vary per portrait and nothing else does:

| In the graph | What it is |
|---|---|
| node `2`, `inputs.text` | the positive prompt — the literal `{{PROMPT}}` here, substituted per request |
| node `3`, `inputs.text` | the negative prompt |
| node `5`, `inputs.seed` | the seed, derived from the person's ID so a record always yields the same face |

## Reproducing any portrait in this repository

You do not have to guess: **each file carries the exact prompt, negative, seed and
model that produced it**, in its XMP packet.

```sh
exiftool -Description -Negative -Seed -Model portraits/l/np-04.avif
```

Put those three values into the graph, run it on the checkpoint named in `Model`,
and you get that face back.

```sh
# start ComfyUI plainly, with the checkpoint in models/checkpoints/
python main.py --listen 127.0.0.1 --port 8188

# submit the graph
curl -X POST http://127.0.0.1:8188/prompt \
  -H 'Content-Type: application/json' \
  -d "$(python3 - <<'PY'
import json
wf = json.load(open("comfyui/workflow_api.json"))
wf["2"]["inputs"]["text"] = "…the Description from the file…"
wf["3"]["inputs"]["text"] = "…the Negative from the file…"
wf["5"]["inputs"]["seed"] = 0  # the Seed from the file
print(json.dumps({"prompt": wf}))
PY
)"
```

## How a prompt is built

Prompts are assembled from the record, never written by hand, which is what keeps
the cast consistent and keeps free text out of a model that has no content filter.
Each one has two halves:

1. **The person**, straight from their JSON — age, sex, heritage, skin, hair
   colour and style, build, and any recorded headwear. This half is why the
   portrait matches the record.
2. **The look**, chosen deterministically from the person's ID — the kind of
   photograph it is (a selfie, a candid, an environmental portrait, 35 mm film, an
   editorial frame), the setting, the light, the framing and the lens. This half
   is why four thousand portraits do not look like one studio session.

Because the look is a function of the ID and not of the description, two people
with similar records still get visibly different photographs, and the same record
always gets the same one.

The negative prompt is shared and is aimed at the failure modes this model
actually has: extra limbs and fingers, a second person in frame, framed pictures
on walls, printed lettering and logos, and glamour retouching.
