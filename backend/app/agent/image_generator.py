from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List, Tuple

from app.schemas.article import ImageRequirement
from app.schemas.image import ImageRequest

if TYPE_CHECKING:
    from app.services.image_service_strategy import ImageResult


class ParallelImageGenerator:
    """并行配图生成器"""

    def __init__(self, image_service_strategy, max_concurrency: int, fail_fast: bool):
        self.image_service_strategy = image_service_strategy
        self.max_concurrency = max(1, max_concurrency)
        self.fail_fast = fail_fast

    async def generate(
        self,
        requirements: List[ImageRequirement],
    ) -> List[Tuple[ImageRequirement, ImageResult]]:
        """并行生成图片，按输入顺序返回结果"""
        if not requirements:
            return []

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _generate_single(requirement: ImageRequirement):
            async with semaphore:
                image_request = ImageRequest(   # type: ignore
                    keywords=requirement.keywords,
                    prompt=requirement.prompt,
                    position=requirement.position,
                    type=requirement.type,
                )
                result = await self.image_service_strategy.get_image_and_upload(
                    requirement.image_source,
                    image_request,
                )
                return requirement, result

        results = await asyncio.gather(
            *[_generate_single(requirement) for requirement in requirements],
            return_exceptions=True,
        )

        generated_pairs: List[Tuple[ImageRequirement, object]] = []
        first_error = None
        for item in results:
            if isinstance(item, Exception):
                if first_error is None:
                    first_error = item
                continue
            generated_pairs.append(item)

        if first_error and (self.fail_fast or not generated_pairs):
            raise first_error
        return generated_pairs
