class BaseJudgeAdapter:
    """
    Base class for Online Judge platform adapters.
    Each platform implements fetch_profile and fetch_submissions.
    """
    def __init__(self, name):
        self.name = name

    def fetch_profile(self, handle):
        """
        Returns a dict:
        {
            "acAll": int,
            "attAll": int,
            "ac1d": int,
            "ac7d": int,
            "ac30d": int,
            "avatar": str
        }
        """
        raise NotImplementedError

    def fetch_submissions(self, handle, limit=100):
        """
        Returns a list of unified submission dicts:
        [
            {
                "time": int (epoch ms),
                "oj": str,
                "probNum": str,
                "problemName": str,
                "status": str (e.g. 'Accepted', 'Wrong Answer'),
                "is_ac": bool,
                "language": str
            }
        ]
        """
        raise NotImplementedError

