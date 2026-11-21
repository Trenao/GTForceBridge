import unittest

from gtforce_bridge.reconnect import WheelLink


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Reconnect(unittest.TestCase):
    def make(self, reopen_results):
        clk = Clock()
        events = []
        results = list(reopen_results)
        link = WheelLink(lambda: results.pop(0) if results else None,
                         lambda: events.append("lost"),
                         lambda w: events.append(("back", w)), retry_s=1.0, clock=clk)
        return link, clk, events

    def test_stays_connected(self):
        link, _, events = self.make([])
        for _ in range(5):
            self.assertTrue(link.poll(True))
        self.assertEqual(events, [])

    def test_lost_once_then_retries_with_interval_then_back(self):
        link, clk, events = self.make([None, "novo"])
        self.assertFalse(link.poll(False))          # perdeu
        self.assertFalse(link.poll(False))          # ainda dentro do intervalo
        self.assertEqual(events, ["lost"])
        clk.t = 1.1
        self.assertFalse(link.poll(False))          # 1ª tentativa falha
        clk.t = 1.5
        self.assertFalse(link.poll(False))          # respeita o intervalo
        clk.t = 2.2
        self.assertTrue(link.poll(False))           # 2ª tentativa acerta
        self.assertEqual(events, ["lost", ("back", "novo")])
        self.assertEqual(link.reconnects, 1)

    def test_exception_in_reopen_is_not_fatal(self):
        clk = Clock()
        link = WheelLink(lambda: (_ for _ in ()).throw(RuntimeError("x")),
                         lambda: None, lambda w: None, retry_s=0.5, clock=clk)
        link.poll(False)
        clk.t = 1.0
        self.assertFalse(link.poll(False))


if __name__ == "__main__":
    unittest.main()
