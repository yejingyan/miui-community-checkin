#!/usr/bin/env python3
import unittest
from pathlib import Path
from unittest import mock

import miui_daily_orchestrator as orch


class TestDailyOrchestrator(unittest.TestCase):
    def test_run_python_step_uses_system_python_for_playwright_entrypoint(self):
        with mock.patch('subprocess.run') as run:
            run.return_value = mock.Mock(returncode=0, stdout='OK\n')
            code = orch.run_python_step('miui_daily_playwright.py')
        self.assertEqual(code, 0)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], orch.sys.executable)
        self.assertEqual(args[0][1], 'miui_daily_playwright.py')
        self.assertEqual(kwargs['cwd'], str(orch.BASE))

    def test_login_expired_exit_triggers_cookie_refresh_and_retry(self):
        calls = []

        def fake_step(script):
            calls.append(script)
            if calls == ['miui_daily_playwright.py']:
                orch.LAST_OUTPUT = 'H5 主签到结果：登录态失效\n额外任务结果：登录态失效\n'
                return 3
            if script == 'refresh_cookie_auto.py':
                orch.LAST_OUTPUT = 'MIUI_COOKIE_REFRESH_OK\n'
                return 0
            if calls[-2:] == ['refresh_cookie_auto.py', 'miui_daily_playwright.py']:
                orch.LAST_OUTPUT = 'H5 主签到结果：需人工验证\n额外任务结果：成功\n'
                return 2
            raise AssertionError(f'unexpected calls: {calls}')

        with mock.patch.object(orch, 'run_python_step', side_effect=fake_step):
            code = orch.main([])

        self.assertEqual(code, 2)
        self.assertEqual(calls, ['miui_daily_playwright.py', 'refresh_cookie_auto.py', 'miui_daily_playwright.py'])

    def test_human_verify_exit_does_not_refresh_cookie(self):
        calls = []

        def fake_step(script):
            calls.append(script)
            orch.LAST_OUTPUT = 'H5 主签到结果：需人工验证\n额外任务结果：成功\n'
            return 2

        with mock.patch.object(orch, 'run_python_step', side_effect=fake_step):
            code = orch.main([])

        self.assertEqual(code, 2)
        self.assertEqual(calls, ['miui_daily_playwright.py'])


if __name__ == '__main__':
    unittest.main()
