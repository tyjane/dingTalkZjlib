import logging

import requests


class TrafficAPI:
    def __init__(
        self,
        primary_url,
        backup_url,
        payload,
        headers,
        timeout=30,
    ):
        self.primary_url = primary_url
        self.backup_url = backup_url
        self.payload = payload
        self.headers = headers
        self.timeout = timeout

    def fetch_flow_data(self, use_backup=False):
        """获取人流数据"""
        url = self.backup_url if use_backup else self.primary_url

        try:
            response = requests.post(
                url,
                json=self.payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            logging.error(
                "请求失败 %s: %s",
                "(备用接口)" if use_backup else "(主接口)",
                exc,
            )
            return None
