import requests


def get_content_from_url(url, parameters=None):
    if parameters is None:
        parameters = {}

    res = requests.get(url, params=parameters)
    return res.content
