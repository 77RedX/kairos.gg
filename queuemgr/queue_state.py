class QueueState:

    def __init__(self):
        self.user_queues = {}
        self.auto_queues = {}
        self.history = {}
        self.current_track = {}
        self.stopped = set()

    def user_q(self, gid):
        return self.user_queues.setdefault(gid, [])

    def auto_q(self, gid):
        return self.auto_queues.setdefault(gid, [])

    def history_set(self, gid):
        return self.history.setdefault(gid, set())