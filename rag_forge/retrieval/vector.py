"""
向量检索模块。

用 Chroma 的 similarity_search_with_score 检索，L2 距离转 0~1 分数。
"""

def vector_search(query: str, vectordb, top_k: int = 6):
    """
    向量检索，返回 [(content, score, source)]，score 0~1。
    """
    vector_results = vectordb.similarity_search_with_score(query, k=top_k)

    # 把 L2 距离转为 0~1 的相似度分数（1 = 最相似）
    vector_scored = []
    if vector_results:
        # 找出距离的最小值和最大值，做归一化
        distances = [d for _, d in vector_results]
        min_dist, max_dist = min(distances), max(distances)
        spread = max_dist - min_dist
        for doc, dist in vector_results:
            if spread > 0:
                sim = 1 - (dist - min_dist) / spread  # 最近→1，最远→0
            else:
                sim = 1.0  # 所有距离相等
            source = doc.metadata.get("source", "")
            vector_scored.append((sim, doc.page_content, source))
    return vector_scored

    

