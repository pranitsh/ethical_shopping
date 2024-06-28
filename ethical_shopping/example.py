import requests 
from urllib.parse import quote_plus


def use_runner(search):
    """
    Calls a Google Cloud Function to gather online documents related to a company.

    Args:
        search (str): The name of the company to search for.

    Result:
        list[str]: a list of the document strings

    Example:
        >>> use_runner("Levi Strauss and Co.")
    """
    url = "https://us-east4-main-403719.cloudfunctions.net/company-get-document-text"


    headers = {"Authorization": f"Bearer"}
    request_body = {'company': quote_plus(search)}

    try:
        response = requests.post(url, headers=headers, json=request_body)
        response.raise_for_status()  # Raise an exception for HTTP errors
        documents = response.json()
        return documents['result']
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")


if __name__ == "__main__":
    import doctest
    doctest.testmod()
