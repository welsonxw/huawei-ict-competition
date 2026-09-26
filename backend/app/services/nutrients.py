"""Oxide <-> elemental conversion. Fertiliser labels give P2O5 and K2O, not elemental P and K."""
P_PER_P2O5 = 0.436
K_PER_K2O = 0.83


def p2o5_to_p(p2o5):
    return p2o5 * P_PER_P2O5


def p_to_p2o5(p):
    return p / P_PER_P2O5


def k2o_to_k(k2o):
    return k2o * K_PER_K2O


def k_to_k2o(k):
    return k / K_PER_K2O


def to_oxide(req, form="oxide"):
    """Normalise a requirement dict to {n, p2o5, k2o}. Elemental input uses keys n, p, k."""
    if form == "elemental":
        return {"n": req["n"], "p2o5": p_to_p2o5(req["p"]), "k2o": k_to_k2o(req["k"])}
    return {"n": req["n"], "p2o5": req["p2o5"], "k2o": req["k2o"]}
