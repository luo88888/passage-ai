class ArticleConstant:
    """文章相关常量"""
    
    SSE_TIMEOUT_MS = 30 * 60 * 1000        # SSE 连接超时（30分钟）
    SSE_RECONNECT_TIME_MS = 3000            # SSE 重连时间（3秒）
    
    PEXELS_API_URL = "https://api.pexels.com/v1/search"
    PEXELS_PER_PAGE = 1
    PEXELS_ORIENTATION_LANDSCAPE = "landscape"
    
    PICSUM_URL_TEMPLATE = "https://picsum.photos/800/600?random={}"
