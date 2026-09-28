"""
报告助手第一步分支问卷的结构校验（纯函数，可离线单测，见 `tests/test_study_wizard_tree.py`）

问卷是一棵由后台拼出来的树：第一题的每个选项要么弹出下一题、要么判定出一类研究。
后台每保存一次都可能把它拼坏，而拼坏的表现全在官网上、且都很温和：

- 选项两头都空 → 用户点了没反应，匹配结果卡片停在上一次的内容上
- 两道题互相指 → 前台逐层往下走，永远走不到结果（前台有防环，但那只是不死循环）
- 指向停用 / 不存在的研究类型 → 结果卡片整块消失，第二步没有 checklist 可展开

所以这些在保存时一次拦下，报错里带上题目与选项标识，管理员能直接定位到哪一格填错了。
「孤立的题」（哪条路径都走不到）只警告不拦：先建好题、再挂到树上是正常的编辑顺序。
"""

from module_action.entity.vo.action_vo import WizardQuestionModel


def check_wizard_tree(
    questions: list[WizardQuestionModel], type_keys: set[str]
) -> tuple[list[str], list[str]]:
    """
    校验整棵问卷树

    :param questions: 全部问题（含选项）
    :param type_keys: 启用中的研究类型标识
    :return: (错误, 警告)。错误非空时不应保存
    """
    errors: list[str] = []
    warnings: list[str] = []
    by_id = {q.question_id: q for q in questions}

    roots = [q for q in questions if q.is_root == '1']
    if not roots:
        errors.append('没有第一题：请把其中一道题设为「第一题」')
    elif len(roots) > 1:
        errors.append('第一题只能有一道：' + '、'.join(q.q_key for q in roots))

    for q in questions:
        seen: set[str] = set()
        for o in q.options:
            where = f'「{q.q_key}」的选项「{o.opt_key}」'
            if o.opt_key in seen:
                errors.append(f'「{q.q_key}」里选项标识 {o.opt_key} 重复')
            seen.add(o.opt_key)
            has_next = o.next_question_id is not None
            has_result = bool(o.result_type_key)
            if has_next and has_result:
                errors.append(f'{where}既指向下一题又给了判定结果，只能二选一')
            elif not has_next and not has_result:
                errors.append(f'{where}既没有下一题也没有判定结果，用户选了会停在原地')
            elif has_next and o.next_question_id not in by_id:
                errors.append(f'{where}指向的下一题已不存在')
            elif has_result and o.result_type_key not in type_keys:
                errors.append(f'{where}判定的研究类型 {o.result_type_key} 不存在或已停用')

    if len(roots) != 1:
        return errors, warnings

    # 从第一题往下走一遍：找环、找走得到却没有选项的题、记下哪些题走得到
    reached: set[int] = set()

    def walk(qid: int, trail: tuple[int, ...]) -> None:
        if qid in trail:
            loop = ' → '.join(by_id[i].q_key for i in (*trail[trail.index(qid):], qid))
            errors.append(f'问题之间形成了循环：{loop}')
            return
        if qid in reached:
            return
        reached.add(qid)
        q = by_id[qid]
        if not q.options:
            errors.append(f'「{q.q_key}」没有任何选项，走到这一题的用户无路可走')
        for o in q.options:
            if o.next_question_id in by_id and not o.result_type_key:
                walk(o.next_question_id, (*trail, qid))

    walk(roots[0].question_id, ())

    orphans = [q.q_key for q in questions if q.question_id not in reached]
    if orphans:
        warnings.append('以下题目从第一题出发走不到，官网上不会出现：' + '、'.join(orphans))

    return errors, warnings


def result_type_refs(questions: list[WizardQuestionModel], type_key: str) -> list[str]:
    """
    哪些选项把结果判定为这一类研究（删除 / 停用研究类型前的引用检查）

    :param questions: 全部问题（含选项）
    :param type_key: 研究类型标识
    :return: 形如「type / B」的引用位置列表
    """
    return [f'{q.q_key} / {o.opt_key}' for q in questions for o in q.options if o.result_type_key == type_key]
