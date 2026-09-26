"""F_0.5 scoring, exactly as the challenge defines it (macro-average per S1 entity).

Singleton rule: a true-empty entity scores 1.0 iff predicted empty, else 0.0.
"""


def f_beta_entity(pred, true, beta2=0.25):
    """F_0.5 for one S1 entity. pred/true are sets of matched IDs."""
    if not true:
        return 1.0 if not pred else 0.0
    if not pred:
        return 0.0
    tp = len(pred & true)
    if tp == 0:
        return 0.0
    p = tp / len(pred)
    r = tp / len(true)
    return (1 + beta2) * p * r / (beta2 * p + r)


def macro_f_beta(pred_map, true_map, s1_ids):
    """Macro-average F_0.5 over s1_ids. Missing keys => empty prediction/truth."""
    total = 0.0
    for s1 in s1_ids:
        total += f_beta_entity(pred_map.get(s1, set()), true_map.get(s1, set()))
    return total / len(s1_ids) if s1_ids else 0.0


def demo():
    # spec example: pred {a,b,c}, true {a,c} -> 0.714
    got = f_beta_entity({"a", "b", "c"}, {"a", "c"})
    assert abs(got - 0.714) < 0.01, got
    assert f_beta_entity(set(), set()) == 1.0          # correct singleton
    assert f_beta_entity({"x"}, set()) == 0.0          # false merge on singleton
    assert f_beta_entity(set(), {"a"}) == 0.0          # missed everything
    assert f_beta_entity({"a"}, {"a"}) == 1.0          # perfect
    print("metric.demo OK")


if __name__ == "__main__":
    demo()
