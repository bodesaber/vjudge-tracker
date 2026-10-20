from .vjudge import VJudgeAdapter
from .codeforces import CodeforcesAdapter
from .atcoder import AtCoderAdapter
from .cses import CSESAdapter

adapters = {
    "vjudge": VJudgeAdapter(),
    "codeforces": CodeforcesAdapter(),
    "atcoder": AtCoderAdapter(),
    "cses": CSESAdapter()
}

def get_adapter(name):
    return adapters.get(name.lower())
