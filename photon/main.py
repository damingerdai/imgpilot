from io import BytesIO
import base64
from diffusers import AutoPipelineForImage2Image
import torch
import tempfile
from leptonai.photon import Photon, FileParam
from compel import Compel
from PIL import Image
from typing import Union
from fastapi.responses import StreamingResponse


class JPEGResponse(StreamingResponse):
    media_type = "image/jpeg"


class ImgPilot(Photon):
    requirement_dependency = [
        "torch",
        "diffusers",
        "invisible-watermark",
        "compel",
        "Pillow",
    ]

    def init(self):
        cuda_available = torch.cuda.is_available()

        if cuda_available:
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        self.base = AutoPipelineForImage2Image.from_pretrained(
            "SimianLuo/LCM_Dreamshaper_v7",
            torch_dtype=torch.float32,
        )
        if cuda_available:
            self.base.to("cuda")

    def _img_param_to_img(self, param):
        from diffusers.utils import load_image

        if isinstance(param, FileParam):
            file = tempfile.NamedTemporaryFile()
            file.write(param.file.read())
            file.flush()
            param = file.name
        elif isinstance(param, str):
            if not param.startswith("http://") and not param.startswith("https://"):
                # base64
                file = tempfile.NamedTemporaryFile()
                file.write(base64.b64decode(param.encode("ascii")))
                file.flush()
                param = file.name
        else:
            raise ValueError(f"Invalid image param: {param}")
        image = load_image(param).convert("RGB")
        return image

    def _predict(
        self,
        input_image: Image.Image,
        seed: int,
        strength: float,
        steps: int,
        guidance_scale: float,
        width: int,
        height: int,
        lcm_steps: int,
        prompt_embeds: torch.Tensor = None,
    ):
        generator = torch.manual_seed(seed)
        results = self.base(
            prompt_embeds=prompt_embeds,
            generator=generator,
            image=input_image,
            strength=strength,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            original_inference_steps=lcm_steps,
            output_type="pil",
        )
        return results.images[0]

    @Photon.handler(
        "run",
        example={
            "prompt": "Portrait of The Terminator with , glare pose, detailed, intricate, full of colour, cinematic lighting, trending on artstation, 8k, hyperrealistic, focused, extreme details, unreal engine 5, cinematic, masterpiece",
            "seed": 2159232,
            "strength": 0.5,
            "steps": 4,
            "guidance_scale": 8.0,
            "width": 512,
            "height": 512,
            "lcm_steps": 50,
            "input_image": "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",
        },
    )
    def run(
        self,
        prompt: str,
        seed: int,
        strength: float,
        steps: int,
        guidance_scale: float,
        width: int,
        height: int,
        lcm_steps: int,
        input_image: Union[str, FileParam],
    ) -> JPEGResponse:
        compel_proc = Compel(
            tokenizer=self.base.tokenizer,
            text_encoder=self.base.text_encoder,
            truncate_long_prompts=False,
        )
        prompt_embeds = compel_proc(prompt)
        if input_image is not None:
            input_image = self._img_param_to_img(input_image)
        image = self._predict(
            input_image,
            seed,
            strength,
            steps,
            guidance_scale,
            width,
            height,
            lcm_steps,
            prompt_embeds,
        )

        img_io = BytesIO()
        image.save(img_io, format="JPEG")
        img_io.seek(0)
        return JPEGResponse(img_io)


if __name__ == "__main__":
    p = ImgPilot()
    p.launch()
