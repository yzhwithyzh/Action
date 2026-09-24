from config.database import AsyncSessionLocal
from module_action.service.literature_embed_service import MAX_PER_RUN, LiteratureEmbedService
from utils.log_util import logger


async def refresh_stale_embeddings(limit: int = MAX_PER_RUN) -> None:
    """
    补算针灸文献知识库中缺失或过期的检索向量

    后台在「参考文献管理」页改了标题/摘要/病种标签之后，`LiteratureService` 会把该行的
    `embed_hash` 置空 —— **只标记，不当场重算**。理由是保存必须永远快、永不失败：
    「因为一个外部 embedding 端点不通，导致管理员改不了文献」比「向量晚几分钟更新」
    糟得多，而这个库本来就是低频更新的。

    未启用向量检索（`EMBED_ENABLED=false`）时本任务直接空转，不报错 ——
    向量是可选能力，没配置时检索退回 BM25 仍能工作。

    :param limit: 单次最多补算多少篇，剩下的下一轮继续（补算幂等，分几轮跑完等价）
    :return: None
    """
    async with AsyncSessionLocal() as query_db:
        result = await LiteratureEmbedService.refresh_stale_services(query_db, limit=limit)
    if result['failed']:
        logger.warning(
            f'文献向量补算有 {result["failed"]} 篇失败（多为 embedding 端点不可用），'
            f'下一轮会自动重试'
        )
