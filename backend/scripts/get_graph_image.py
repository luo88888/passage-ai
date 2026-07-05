from app.graph.builder import build_article_graph
from app.utils.path_tool import get_abs_path


if __name__ == '__main__':
    # 画图只需图拓扑，无需可运行的 checkpointer（传 None）
    graph = build_article_graph(None)

    # 1. 获取图表的 PNG 二进制数据
    png_data = graph.get_graph().draw_mermaid_png()

    # 2. 将二进制数据写入文件
    output_path = get_abs_path() / "docs" / "graph.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(png_data)
    
    print(f"✅ 图片已成功保存为 {output_path}")