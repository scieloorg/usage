from articlemeta.client import ThriftClient, RestfulClient


def fetch_article_meta_journals(collection='scl', mode='rest'):
    """
    Fetches article metadata from journals.

    Returns
    -------
    list
        A list of article metadata.
    """
    if mode == 'rest':
        am = RestfulClient()
    elif mode == 'thrift':
        am = ThriftClient()
    
    for j in am.journals(collection=collection):
        yield j
