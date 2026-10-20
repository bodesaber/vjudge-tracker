from .vjudge import VJudgeAdapter
from .codeforces import CodeforcesAdapter

adapters = {
    "vjudge": VJudgeAdapter(),
    "codeforces": CodeforcesAdapter()
}

def get_adapter(name):
    return adapters.get(name.lower())
