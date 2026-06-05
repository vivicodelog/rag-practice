"""
关键词检索模块。

jieba 分词 + 关键词匹配，分数归一化到 0~1。
"""

def keyword_search(query: str, all_chunks: list, top_k: int = 10):
    """
    关键词检索，返回 [(content, score, source)]，score 0~1。
    """
    # ========== 2. 关键词匹配（带分数）==========
    kw_scored = []
    if all_chunks:
        try:
            import jieba
            import re
            stop_words = {'问题', '什么', '怎么', '解决', '方案', '方法', '如何'}
            words = [w for w in jieba.lcut(query) if len(w) >= 2 and w not in stop_words]
            if not words:
                words = re.findall(r'[a-zA-Z0-9_]{2,}', query)
        except:
            words = []

        kw_set = set(words)
        # 关键词总长度（用于归一化）
        query_keyword_len = sum(len(kw) for kw in kw_set) if kw_set else 1

        for item in all_chunks:
            content = item["content"] if isinstance(item, dict) else item.page_content
            matched_len = sum(len(kw) for kw in kw_set if kw in content)
            if matched_len > 0:
                kw_score = matched_len / query_keyword_len  # 0~1
                source = item.get("metadata", {}).get("source", "") if isinstance(item, dict) else ""
                kw_scored.append((kw_score, content, source))

    kw_scored.sort(key=lambda x: -x[0])
    return kw_scored[:top_k] 