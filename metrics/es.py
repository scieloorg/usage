import logging

from elasticsearch import Elasticsearch, helpers, NotFoundError
from django.conf import settings

from .utils import index_utils


DEFAULT_ES_INDEX_USAGE_MAPPINGS = {
    "properties": {
        "collection": {
            "type": "keyword"
        },
        "journal": {
            "properties": {
                "scielo_issn": {
                    "type": "keyword"
                },
                "main_title": {
                    "type": "keyword"
                },
                "subject_area_capes": {
                    "type": "keyword"
                },
                "subject_area_wos": {
                    "type": "keyword"
                },
                "acronym": {
                    "type": "keyword"
                },
                "publisher": {
                    "type": "keyword"
                }
            }
        },
        "pid": {
            "type": "keyword"
        },
        "pid_v2": {
            "type": "keyword"
        },
        "pid_v3": {
            "type": "keyword"
        },
        "pid_generic": {
            "type": "keyword"
        },
        "year_of_publication": {
            "type": "integer"
        },
        "media_language": {
            "type": "keyword"
        },
        "country_code": {
            "type": "keyword"
        },
        "date": {
            "type": "date",
            "format": "yyyy-MM-dd"
        },
        "total_requests": {
            "type": "integer"
        },
        "total_investigations": {
            "type": "integer"
        },
        "unique_requests": {
            "type": "integer"
        },
        "unique_investigations": {
            "type": "integer"
        }
    }
}


class ElasticSearchUsageWrapper:
    """
    Wrapper for Elasticsearch usage metrics operations.
    This class provides methods to interact with Elasticsearch for indexing,
    deleting, and managing usage metrics data.
    """

    def __init__(self, url=None, basic_auth=None, api_key=None, verify_certs=False):
        self.client = self.get_elasticsearch_client(url, basic_auth, api_key, verify_certs)


    def get_elasticsearch_client(self, url=None, basic_auth=None, api_key=None, verify_certs=False):
        """
        Create an Elasticsearch client instance using Django settings.

        :param url: Elasticsearch URL. If None, it will be taken from Django settings.
        :param basic_auth: Basic authentication credentials. If None, it will be taken from Django settings.
        :param api_key: API key. If None, it will be taken from Django settings.
        :param verify_certs: Whether to verify SSL certificates. If None, it will be taken from Django settings.
        """
        if not url:
            url = getattr(settings, "ES_URL", None)

        if not basic_auth:
            basic_auth = getattr(settings, "ES_BASIC_AUTH", None)

        if not api_key:
            api_key = getattr(settings, "ES_API_KEY", None)

        if not verify_certs:
            verify_certs = getattr(settings, "ES_VERIFY_CERTS", False)

        if basic_auth:
            client = Elasticsearch(url, basic_auth=basic_auth, verify_certs=verify_certs)
        elif api_key:
            client = Elasticsearch(url, api_key=api_key, verify_certs=verify_certs)
        else:
            client = Elasticsearch(url, verify_certs=verify_certs)

        return client
    

    def ping(self):
        """
        Check if the Elasticsearch client is available.
        Returns True if the client is available, False otherwise.
        """
        try:
            return self.client.ping()
        except Exception as e:
            logging.error(f"Error pinging Elasticsearch client: {e}")
            return False


    def create_index(self, index_name, mappings=None, ping_client=False):
        """
        Create an Elasticsearch index. 

        :param index_name: Name of the index to create.
        :param mappings: Mappings for the index. If None, default mappings will be used.
        :param ping_client: If True, checks if the Elasticsearch client is available before creating the index.
        """
        if ping_client and not self.ping():
            return

        if not mappings:
            mappings = DEFAULT_ES_INDEX_USAGE_MAPPINGS

        resp = self.client.indices.create(
            index=index_name,
            mappings=mappings,
        )
        logging.info(f"Index {index_name} created: {resp}")


    def create_index_if_not_exists(self, index_name, mappings=None, ping_client=False):
        """
        Create an Elasticsearch index if it does not already exist.

        :param index_name: Name of the index to create.
        :param mappings: Mappings for the index. If None, default mappings will be used.
        :param ping_client: If True, checks if the Elasticsearch client is available before creating the index.
        """
        if ping_client and not self.ping():
            return

        if not self.client.indices.exists(index=index_name):
            self.create_index(index_name, mappings, ping_client)
        else:
            logging.info(f"Index {index_name} already exists. Skipping creation.")


    def delete_index(self, index_name, ping_client=False):
        """
        Delete an Elasticsearch index.

        :param index_name: Name of the index to delete.
        :param ping_client: If True, checks if the Elasticsearch client is available before deleting the index.
        """
        if ping_client and not self.ping():
            return
        
        self.client.indices.delete(index=index_name)


    def index_document(self, index_name, doc_id, document, ping_client=False):
        """
        Index a document in Elasticsearch.

        :param index_name: Name of the index.
        :param doc_id: ID of the document.
        :param document: Document to index.
        :param ping_client: If True, checks if the Elasticsearch client is available before indexing the document.
        """
        if ping_client and not self.ping():
            return
            
        self.client.index(index=index_name, id=doc_id, document=document)


    def index_documents(self, index_name, documents, ping_client=False):
        """
        Index multiple documents in Elasticsearch.

        :param index_name: Name of the index.
        :param documents: Dictionary of documents to index, where keys are document IDs and values are the documents.
        :param ping_client: If True, checks if the Elasticsearch client is available before indexing the documents.
        """
        if ping_client and not self.ping():
            return
        
        helpers.bulk(
            self.client,
            (
                {
                    "_index": index_name,
                    "_id": doc_id,
                    "_source": document,
                }
                for doc_id, document in documents.items()
            ),
        )


    def delete_document(self, index_name, doc_id, ping_client=False):
        """
        Delete a document from Elasticsearch.

        :param index_name: Name of the index.
        :param doc_id: ID of the document to delete.
        :param ping_client: If True, checks if the Elasticsearch client is available before deleting the document.
        """
        if ping_client and not self.ping():
            return

        try:
            self.client.delete(index=index_name, id=doc_id)
        except NotFoundError as e:
            logging.error(f"Failed to delete document {doc_id} from Elasticsearch: {e}")


    def delete_documents(self, index_name, doc_ids, ping_client=False):
        """
        Delete multiple documents from Elasticsearch using bulk.
        :param index_name: Name of the index.
        :param doc_ids: List of document IDs to delete.
        :param ping_client: If True, checks if the Elasticsearch client is available before deleting the documents.
        """
        if ping_client and not self.ping():
            return
                    
        actions = (
            {
                "_op_type": "delete",
                "_index": index_name,
                "_id": doc_id,
            }
            for doc_id in doc_ids
        )

        try:
            helpers.bulk(self.client, actions)
        except helpers.BulkIndexError as e:
            logging.error(f"BulkIndexError occurred: {e.errors}")


    def delete_documents_by_key(self, index_name, data, ping_client=False):
        """
        Delete multiple documents from Elasticsearch based on specific key-value pairs.

        :param index_name: Name of the index.
        :param data: Dictionary where keys are field names and values are single values or lists of values.
        :param ping_client: If True, checks if the Elasticsearch client is available before deleting the documents.
        """
        if ping_client and not self.ping():
            return

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "terms": {
                                key: values if isinstance(values, list) else [values]
                            }
                        }
                        for key, values in data.items()
                    ]
                }
            }
        }

        try:
            self.client.delete_by_query(index=index_name, body=query)
            return True
        except Exception as e:
            logging.error(f"Failed to delete documents: {e}")

        return False


    def fetch_and_update_documents_locally(self, index_name, documents, batch_size=5000, ping_client=False):
        """
        Fetch existing documents from Elasticsearch and update local documents with accumulated metrics.
        This function retrieves documents from Elasticsearch in batches and merges their metric fields
        with the provided local documents. The merge operation adds values for specific metric fields
        or sets them if they don't exist in the local documents.

        Args:
            index_name (str): Name of the Elasticsearch index to fetch documents from.
            documents (dict): Dictionary of documents to be updated, where keys are document IDs and values
                are dictionaries containing metric data.
            batch_size (int, optional): Number of documents to fetch in each batch from Elasticsearch.
                Defaults to 5000.
            ping_client (bool, optional): If True, checks if the Elasticsearch client is available before
                fetching documents. Defaults to False.
        
        Returns:
            None: The function modifies the input documents dictionary in-place.
        """
        if ping_client and not self.ping():
            return

        existing_docs = {}
        ids = list(documents.keys())

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i+batch_size]
            resp = self.client.mget(index=index_name, ids=batch_ids)
            for doc in resp.get('docs', []):
                if doc.get('found'):
                    existing_docs[doc['_id']] = doc['_source']
        logging.info(f'Found {len(existing_docs)} existing documents in Elasticsearch for update.')

        for doc_id, existing in existing_docs.items():
            current = documents[doc_id]
            for field in [
                "total_requests",
                "unique_requests",
                "total_investigations",
                "unique_investigations",
            ]:
                if field in existing and field in current:
                    current[field] += existing[field]
                elif field in existing:
                    current[field] = existing[field]
        

    def export_to_index(self, index_name, data, batch_size=5000, ping_client=False):
        """
        Export data to Elasticsearch index in bulk operations.
        This function converts input data to index documents, processes them locally,
        and then indexes them to Elasticsearch in batches to optimize performance.
        
        Args:
            index_name (str): Name of the Elasticsearch index to export data to.
            data: The data to be exported to the Elasticsearch index
            batch_size (int, optional): Number of documents to process in each bulk operation.
                Defaults to 5000.
            ping_client (bool, optional): If True, checks if the Elasticsearch client is available

        Returns:
            None: Function performs side effects by indexing data to Elasticsearch
        """
        if ping_client and not self.ping():
            return
        
        bulk_data = []
        documents = index_utils.convert_to_index_documents(data)
        self.fetch_and_update_documents_locally(index_name=index_name, documents=documents)

        for key, metric_data in documents.items():
            metric_data['pid'] = metric_data.get('pid_v3') or metric_data.get('pid_v2') or metric_data.get('pid_generic', '')
            bulk_data.append({
                "_id": key,
                "_source": metric_data,
            })

            if len(bulk_data) >= batch_size:
                self.index_documents(
                    index_name=index_name,
                    documents={doc["_id"]: doc["_source"] for doc in bulk_data},
                )
                bulk_data = []

        self.index_documents(
            index_name=index_name,
            documents={doc["_id"]: doc["_source"] for doc in bulk_data},
        )
