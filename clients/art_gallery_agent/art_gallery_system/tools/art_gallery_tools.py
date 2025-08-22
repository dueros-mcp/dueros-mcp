"""艺术画廊工具：艺术品检索与设备交互。"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from art_gallery_system.tools.handoff_tools import transfer_to_chat
from art_gallery_system.configuration import Configuration
from elasticsearch import Elasticsearch
import asyncio


# ============= Pydantic Schemas =============
class PictureSearchInput(BaseModel):
    """图片搜索输入参数。"""
    query: Optional[str] = Field(default=None, description="搜索关键词，用于查找相关艺术作品")
    artist: Optional[str] = Field(default=None, description="艺术家名称，可用于筛选特定艺术家的作品")
    style: Optional[str] = Field(default=None, description="艺术风格，如印象派、现代主义等")
    period: Optional[str] = Field(default=None, description="时期，如文艺复兴、19世纪等")
    limit: int = Field(default=10, description="返回结果数量限制，默认10个")


class QuestionInput(BaseModel):
    """提问输入参数。"""
    question: str = Field(description="要向用户提出的问题")
    options: Optional[List[str]] = Field(default=None, description="可选的答案选项列表")

def _get_es_client() -> Optional[Elasticsearch]:
    """获取 ES 客户端实例。"""
    try:
        config = Configuration.from_context()
        
        es_config = {
            'hosts': [config.elasticsearch_host],
            'request_timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True
        }
        
        if config.elasticsearch_username and config.elasticsearch_password:
            es_config['http_auth'] = (
                config.elasticsearch_username, 
                config.elasticsearch_password
            )
        
        es_client = Elasticsearch(**es_config)
        print(f"[ES工具] 连接到: {config.elasticsearch_host}")
        return es_client
        
    except Exception as e:
        print(f"[ES工具] 初始化失败: {e}")
        return None

# 添加艺术作品搜索工具，提供完整的ES查询功能
@tool(args_schema=PictureSearchInput)
async def search_artworks(
    query: Optional[str] = None,
    artist: Optional[str] = None,
    style: Optional[str] = None,
    period: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """搜索艺术作品，支持多条件组合。

    Args:
        query: 关键词（作品名、描述等）
        artist: 艺术家
        style: 风格或材质
        period: 时期
        limit: 返回数量上限，默认 10

    Returns:
        结构化结果字典（含 `status`、`total`、`artworks`、`message`）。
    """
    try:
        # 获取ES客户端
        es_client = _get_es_client()
        if not es_client:
            return {
                "status": "error",
                "total": 0,
                "artworks": [],
                "message": "ES客户端初始化失败"
            }
        
        config = Configuration.from_context()
        
        # 构建查询 - 根据实际索引结构
        must_queries = []
        
        # 主查询 - 搜索可索引的文本字段
        # 根据新mapping，artwork_name和artist现在都是text类型，使用wordseg-basic分析器
        if query:
            must_queries.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "artwork_name^3",           # artwork_name (text, wordseg-basic)
                        "artwork_description^2",    # 作品描述 (text, wordseg-basic)
                        "artwork_abstract^1.5",     # 作品摘要 (text, wordseg-basic)
                        "artist^1"                  # 艺术家 (text, wordseg-basic)
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "operator": "or"
                }
            })
        
        # 艺术家过滤 - 使用match查询，因为artist现在是text类型
        if artist:
            must_queries.append({
                "match": {
                    "artist": artist
                }
            })
        
        # 时期过滤 - 精确匹配，period仍是keyword类型
        if period:
            must_queries.append({
                "term": {
                    "period": period
                }
            })
        
        # 风格过滤 - 可以匹配material、styles等字段
        if style:
            must_queries.append({
                "bool": {
                    "should": [
                        {"term": {"material": style}},      # 材质 (keyword)
                        {"term": {"styles": style}}         # 风格 (keyword)
                    ],
                    "minimum_should_match": 1
                }
            })
        
        search_body = {
            "query": {
                "bool": {
                    "must": must_queries if must_queries else [{"match_all": {}}]
                }
            },
            "size": limit,
            "_source": True,
            "sort": [
                {"_score": {"order": "desc"}},
                {"display_order": {"order": "asc"}}  # 按展示顺序排序
            ]
        }
        
        # 执行搜索 - 使用 asyncio.to_thread 避免阻塞事件循环
        response = await asyncio.to_thread(
            es_client.search,
            index=config.elasticsearch_index_artwork,
            body=search_body
        )
        
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            result = {
                "id": source.get('artwork_id', hit['_id']),
                "score": hit['_score'],
                "title": source.get('artwork_name', ''),
                "artist": source.get('artist', ''),
                "period": source.get('period', ''),
                "material": source.get('material', ''),  # 材质信息
                "description": source.get('artwork_description', ''),
                "abstract": source.get('artwork_abstract', ''),  # 作品摘要
                "image_url": source.get('high_res_image_url', ''),  # 高清图片
                "thumbnail_url": source.get('thumbnail_url', ''),  # 缩略图
                "collection_unit": source.get('collection_unit', ''),  # 收藏单位
                "display_order": source.get('display_order', 0),
                "update_time": source.get('update_time', ''),
                "video_url": source.get('video_url', ''),
                # 新增的视觉属性字段
                "width_cm": source.get('width_cm'),
                "height_cm": source.get('height_cm'),
                "aspect_ratio": source.get('aspect_ratio', ''),
                "dominant_colors": source.get('dominant_colors', []),
                "frame_colors": source.get('frame_colors', []),
                "brightness_level": source.get('brightness_level', ''),
                "color_temperature": source.get('color_temperature', ''),
                "colorfulness": source.get('colorfulness'),
                # 新增的语义字段
                "styles": source.get('styles', []),
                "themes": source.get('themes', []),
                "moods": source.get('moods', []),
                "recommended_rooms": source.get('recommended_rooms', []),
                "lighting_suitability": source.get('lighting_suitability', ''),
                "data_source": "elasticsearch"
            }
            results.append(result)
        
        print(f"[ES工具] 艺术作品搜索: 查询'{query}', 找到 {len(results)} 个结果")
        
        return {
            "status": "success",
            "total": len(results),
            "artworks": results,
            "message": f"成功查询到 {len(results)} 个艺术作品"
        }
        
    except Exception as e:
        error_msg = f"艺术作品搜索失败: {str(e)}"
        print(f"[艺术画廊工具] {error_msg}")
        return {
            "status": "error",
            "total": 0,
            "artworks": [],
            "message": error_msg
        }


# ============= Tool Lists =============
# 艺术画廊工具集合 - 包含handoff工具
# 注意：MCP工具将在运行时动态添加
ART_GALLERY_TOOLS = [
    search_artworks, 
    transfer_to_chat,        # 可以转移到聊天助手
]


# ============= Async Tool Loading Function =============
async def get_art_gallery_tools_with_mcp() -> List:
    """获取包含MCP工具的艺术画廊工具集合"""
    from art_gallery_system.tools.mcp_client import get_tools
    
    # 获取基础工具
    tools = ART_GALLERY_TOOLS.copy()
    
    # 添加MCP工具
    try:
        mcp_tools = await get_tools()
        tools.extend(mcp_tools)
        print(f"[艺术画廊] 添加了 {len(mcp_tools)} 个MCP工具")
    except Exception as e:
        print(f"[艺术画廊] 获取MCP工具失败: {e}")
    
    return tools 