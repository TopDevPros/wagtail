# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import datetime
import json
import os
import unittest

import mock
from django.db.models import Q
from django.test import TestCase
from elasticsearch.serializer import JSONSerializer

from wagtail.tests.search import models
from wagtail.wagtailsearch.backends import get_search_backend
from wagtail.wagtailsearch.backends.elasticsearch5 import Elasticsearch5SearchBackend

from .elasticsearch_common_tests import ElasticsearchCommonSearchBackendTests
from .test_backends import BackendTests


class TestElasticsearch5SearchBackend(BackendTests, ElasticsearchCommonSearchBackendTests, TestCase):
    backend_path = 'wagtail.wagtailsearch.backends.elasticsearch5'

    # Broken
    @unittest.expectedFailure
    def test_filter_in_values_list_subquery(self):
        super(TestElasticsearch5SearchBackend, self).test_filter_in_values_list_subquery()

    # Broken
    @unittest.expectedFailure
    def test_order_by_non_filterable_field(self):
        super(TestElasticsearch5SearchBackend, self).test_order_by_non_filterable_field()

    # Broken
    @unittest.expectedFailure
    def test_delete(self):
        super(TestElasticsearch5SearchBackend, self).test_delete()


class TestElasticsearch5SearchQuery(TestCase):
    def assertDictEqual(self, a, b):
        default = JSONSerializer().default
        self.assertEqual(
            json.dumps(a, sort_keys=True, default=default), json.dumps(b, sort_keys=True, default=default)
        )

    query_class = Elasticsearch5SearchBackend.query_class

    def test_simple(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), "Hello")

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_none_query_string(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), None)

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'match_all': {}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_and_operator(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), "Hello", operator='and')

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials'], 'operator': 'and'}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_filter(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title="Test"), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'term': {'title_filter': 'Test'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_and_filter(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title="Test", publication_date=datetime.date(2017, 10, 18)), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'bool': {'must': [{'term': {'publication_date_filter': '2017-10-18'}}, {'term': {'title_filter': 'Test'}}]}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}

        # Make sure field filters are sorted (as they can be in any order which may cause false positives)
        query = query.get_query()
        field_filters = query['bool']['filter'][1]['bool']['must']
        field_filters[:] = sorted(field_filters, key=lambda f: list(f['term'].keys())[0])

        self.assertDictEqual(query, expected_result)

    def test_or_filter(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(Q(title="Test") | Q(publication_date=datetime.date(2017, 10, 18))), "Hello")

        # Make sure field filters are sorted (as they can be in any order which may cause false positives)
        query = query.get_query()
        field_filters = query['bool']['filter'][1]['bool']['should']
        field_filters[:] = sorted(field_filters, key=lambda f: list(f['term'].keys())[0])

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'bool': {'should': [{'term': {'publication_date_filter': '2017-10-18'}}, {'term': {'title_filter': 'Test'}}]}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query, expected_result)

    def test_negated_filter(self):
        # Create a query
        query = self.query_class(models.Book.objects.exclude(publication_date=datetime.date(2017, 10, 18)), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'bool': {'mustNot': {'term': {'publication_date_filter': '2017-10-18'}}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_fields(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), "Hello", fields=['title'])

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'match': {'title': 'Hello'}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_fields_with_and_operator(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), "Hello", fields=['title'], operator='and')

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'match': {'title': {'query': 'Hello', 'operator': 'and'}}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_multiple_fields(self):
        # Create a query
        query = self.query_class(models.Book.objects.all(), "Hello", fields=['title', 'content'])

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'multi_match': {'fields': ['title', 'content'], 'query': 'Hello'}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_multiple_fields_with_and_operator(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.all(), "Hello", fields=['title', 'content'], operator='and'
        )

        # Check it
        expected_result = {'bool': {
            'filter': {'match': {'content_type': 'searchtests.Book'}},
            'must': {'multi_match': {'fields': ['title', 'content'], 'query': 'Hello', 'operator': 'and'}}
        }}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_exact_lookup(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title__exact="Test"), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'term': {'title_filter': 'Test'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_none_lookup(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title=None), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'missing': {'field': 'title_filter'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_isnull_true_lookup(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title__isnull=True), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'missing': {'field': 'title_filter'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_isnull_false_lookup(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title__isnull=False), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'exists': {'field': 'title_filter'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_startswith_lookup(self):
        # Create a query
        query = self.query_class(models.Book.objects.filter(title__startswith="Test"), "Hello")

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'prefix': {'title_filter': 'Test'}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_gt_lookup(self):
        # This also tests conversion of python dates to strings

        # Create a query
        query = self.query_class(
            models.Book.objects.filter(publication_date__gt=datetime.datetime(2014, 4, 29)), "Hello"
        )

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'range': {'publication_date_filter': {'gt': '2014-04-29'}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_lt_lookup(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.filter(publication_date__lt=datetime.datetime(2014, 4, 29)), "Hello"
        )

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'range': {'publication_date_filter': {'lt': '2014-04-29'}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_gte_lookup(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.filter(publication_date__gte=datetime.datetime(2014, 4, 29)), "Hello"
        )

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'range': {'publication_date_filter': {'gte': '2014-04-29'}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_lte_lookup(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.filter(publication_date__lte=datetime.datetime(2014, 4, 29)), "Hello"
        )

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'range': {'publication_date_filter': {'lte': '2014-04-29'}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_range_lookup(self):
        start_date = datetime.datetime(2014, 4, 29)
        end_date = datetime.datetime(2014, 8, 19)

        # Create a query
        query = self.query_class(
            models.Book.objects.filter(publication_date__range=(start_date, end_date)), "Hello"
        )

        # Check it
        expected_result = {'bool': {'filter': [
            {'match': {'content_type': 'searchtests.Book'}},
            {'range': {'publication_date_filter': {'gte': '2014-04-29', 'lte': '2014-08-19'}}}
        ], 'must': {'multi_match': {'query': 'Hello', 'fields': ['_all', '_partials']}}}}
        self.assertDictEqual(query.get_query(), expected_result)

    def test_custom_ordering(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.order_by('publication_date'), "Hello", order_by_relevance=False
        )

        # Check it
        expected_result = [{'publication_date_filter': 'asc'}]
        self.assertDictEqual(query.get_sort(), expected_result)

    def test_custom_ordering_reversed(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.order_by('-publication_date'), "Hello", order_by_relevance=False
        )

        # Check it
        expected_result = [{'publication_date_filter': 'desc'}]
        self.assertDictEqual(query.get_sort(), expected_result)

    def test_custom_ordering_multiple(self):
        # Create a query
        query = self.query_class(
            models.Book.objects.order_by('publication_date', 'number_of_pages'), "Hello", order_by_relevance=False
        )

        # Check it
        expected_result = [{'publication_date_filter': 'asc'}, {'number_of_pages_filter': 'asc'}]
        self.assertDictEqual(query.get_sort(), expected_result)


class TestElasticsearch5SearchResults(TestCase):
    fixtures = ['search']

    def assertDictEqual(self, a, b):
        default = JSONSerializer().default
        self.assertEqual(
            json.dumps(a, sort_keys=True, default=default), json.dumps
        )

    def get_results(self):
        backend = Elasticsearch5SearchBackend({})
        query = mock.MagicMock()
        query.queryset = models.Book.objects.all()
        query.get_query.return_value = 'QUERY'
        query.get_sort.return_value = None
        return backend.results_class(backend, query)

    def construct_search_response(self, results):
        return {
            '_shards': {'failed': 0, 'successful': 5, 'total': 5},
            'hits': {
                'hits': [
                    {
                        '_id': 'searchtests_book:' + str(result),
                        '_index': 'wagtail',
                        '_score': 1,
                        '_type': 'searchtests_book',
                        'fields': {
                            'pk': [str(result)],
                        }
                    }
                    for result in results
                ],
                'max_score': 1,
                'total': len(results)
            },
            'timed_out': False,
            'took': 2
        }

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_basic_search(self, search):
        search.return_value = self.construct_search_response([])
        results = self.get_results()

        list(results)  # Performs search

        search.assert_any_call(
            from_=0,
            body={'query': 'QUERY'},
            _source=False,
            stored_fields='pk',
            index='wagtail__searchtests_book'
        )

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_get_single_item(self, search):
        # Need to return something to prevent index error
        search.return_value = self.construct_search_response([1])
        results = self.get_results()

        results[10]  # Performs search

        search.assert_any_call(
            from_=10,
            body={'query': 'QUERY'},
            _source=False,
            stored_fields='pk',
            index='wagtail__searchtests_book',
            size=1
        )

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_slice_results(self, search):
        search.return_value = self.construct_search_response([])
        results = self.get_results()[1:4]

        list(results)  # Performs search

        search.assert_any_call(
            from_=1,
            body={'query': 'QUERY'},
            _source=False,
            stored_fields='pk',
            index='wagtail__searchtests_book',
            size=3
        )

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_slice_results_multiple_times(self, search):
        search.return_value = self.construct_search_response([])
        results = self.get_results()[10:][:10]

        list(results)  # Performs search

        search.assert_any_call(
            from_=10,
            body={'query': 'QUERY'},
            _source=False,
            stored_fields='pk',
            index='wagtail__searchtests_book',
            size=10
        )

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_slice_results_and_get_item(self, search):
        # Need to return something to prevent index error
        search.return_value = self.construct_search_response([1])
        results = self.get_results()[10:]

        results[10]  # Performs search

        search.assert_any_call(
            from_=20,
            body={'query': 'QUERY'},
            _source=False,
            stored_fields='pk',
            index='wagtail__searchtests_book',
            size=1
        )

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_result_returned(self, search):
        search.return_value = self.construct_search_response([1])
        results = self.get_results()

        self.assertEqual(results[0], models.Book.objects.get(id=1))

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_len_1(self, search):
        search.return_value = self.construct_search_response([1])
        results = self.get_results()

        self.assertEqual(len(results), 1)

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_len_2(self, search):
        search.return_value = self.construct_search_response([1, 2])
        results = self.get_results()

        self.assertEqual(len(results), 2)

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_duplicate_results(self, search):  # Duplicates will not be removed
        search.return_value = self.construct_search_response([1, 1])
        results = list(self.get_results())  # Must cast to list so we only create one query

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], models.Book.objects.get(id=1))
        self.assertEqual(results[1], models.Book.objects.get(id=1))

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_result_order(self, search):
        search.return_value = self.construct_search_response(
            [1, 2, 3]
        )
        results = list(self.get_results())  # Must cast to list so we only create one query

        self.assertEqual(results[0], models.Book.objects.get(id=1))
        self.assertEqual(results[1], models.Book.objects.get(id=2))
        self.assertEqual(results[2], models.Book.objects.get(id=3))

    @mock.patch('elasticsearch.Elasticsearch.search')
    def test_result_order_2(self, search):
        search.return_value = self.construct_search_response(
            [3, 2, 1]
        )
        results = list(self.get_results())  # Must cast to list so we only create one query

        self.assertEqual(results[0], models.Book.objects.get(id=3))
        self.assertEqual(results[1], models.Book.objects.get(id=2))
        self.assertEqual(results[2], models.Book.objects.get(id=1))


class TestElasticsearch5Mapping(TestCase):
    fixtures = ['search']

    def assertDictEqual(self, a, b):
        default = JSONSerializer().default
        self.assertEqual(
            json.dumps(a, sort_keys=True, default=default), json.dumps(b, sort_keys=True, default=default)
        )

    def setUp(self):
        # Create ES mapping
        self.es_mapping = Elasticsearch5SearchBackend.mapping_class(models.Book)

        # Create ES document
        self.obj = models.Book.objects.get(id=4)

    def test_get_document_type(self):
        self.assertEqual(self.es_mapping.get_document_type(), 'searchtests_book')

    def test_get_mapping(self):
        # Build mapping
        mapping = self.es_mapping.get_mapping()

        # Check
        expected_result = {
            'searchtests_book': {
                'properties': {
                    'pk': {'type': 'keyword', 'store': True, 'include_in_all': False},
                    'content_type': {'type': 'keyword', 'include_in_all': False},
                    '_partials': {'analyzer': 'edgengram_analyzer', 'search_analyzer': 'standard', 'include_in_all': False, 'type': 'text'},
                    'title': {'type': 'text', 'boost': 2.0, 'include_in_all': True, 'analyzer': 'edgengram_analyzer', 'search_analyzer': 'standard'},
                    'title_filter': {'type': 'keyword', 'include_in_all': False},
                    'authors': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'include_in_all': True},
                            'date_of_birth_filter': {'type': 'date', 'include_in_all': False},
                        },
                    },
                    'publication_date_filter': {'type': 'date', 'include_in_all': False},
                    'number_of_pages_filter': {'type': 'integer', 'include_in_all': False},
                    'tags': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'include_in_all': True},
                            'slug_filter': {'type': 'keyword', 'include_in_all': False},
                        },
                    }
                }
            }
        }

        self.assertDictEqual(mapping, expected_result)

    def test_get_document_id(self):
        self.assertEqual(self.es_mapping.get_document_id(self.obj), 'searchtests_book:' + str(self.obj.pk))

    def test_get_document(self):
        # Get document
        document = self.es_mapping.get_document(self.obj)

        # Sort partials
        if '_partials' in document:
            document['_partials'].sort()

        # Check
        expected_result = {
            'pk': '4',
            'content_type': ["searchtests.Book"],
            '_partials': ['The Fellowship of the Ring'],
            'title': 'The Fellowship of the Ring',
            'title_filter': 'The Fellowship of the Ring',
            'authors': [
                {
                    'name': 'J. R. R. Tolkien',
                    'date_of_birth_filter': datetime.date(1892, 1, 3)
                }
            ],
            'publication_date_filter': datetime.date(1954, 7, 29),
            'number_of_pages_filter': 423,
            'tags': []
        }

        self.assertDictEqual(document, expected_result)


class TestElasticsearch5MappingInheritance(TestCase):
    fixtures = ['search']

    def assertDictEqual(self, a, b):
        default = JSONSerializer().default
        self.assertEqual(
            json.dumps(a, sort_keys=True, default=default), json.dumps(b, sort_keys=True, default=default)
        )

    def setUp(self):
        # Create ES mapping
        self.es_mapping = Elasticsearch5SearchBackend.mapping_class(models.Novel)

        self.obj = models.Novel.objects.get(id=4)

    def test_get_document_type(self):
        self.assertEqual(self.es_mapping.get_document_type(), 'searchtests_book_searchtests_novel')

    def test_get_mapping(self):
        # Build mapping
        mapping = self.es_mapping.get_mapping()

        # Check
        expected_result = {
            'searchtests_book_searchtests_novel': {
                'properties': {
                    # New
                    'searchtests_novel__setting': {'type': 'text', 'include_in_all': True, 'analyzer': 'edgengram_analyzer', 'search_analyzer': 'standard'},
                    'searchtests_novel__protagonist': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'boost': 0.5, 'include_in_all': True}
                        }
                    },
                    'searchtests_novel__characters': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'boost': 0.25, 'include_in_all': True}
                        }
                    },

                    # Inherited
                    'pk': {'type': 'keyword', 'store': True, 'include_in_all': False},
                    'content_type': {'type': 'keyword', 'include_in_all': False},
                    '_partials': {'analyzer': 'edgengram_analyzer', 'search_analyzer': 'standard', 'include_in_all': False, 'type': 'text'},
                    'title': {'type': 'text', 'boost': 2.0, 'include_in_all': True, 'analyzer': 'edgengram_analyzer', 'search_analyzer': 'standard'},
                    'title_filter': {'type': 'keyword', 'include_in_all': False},
                    'authors': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'include_in_all': True},
                            'date_of_birth_filter': {'type': 'date', 'include_in_all': False},
                        },
                    },
                    'publication_date_filter': {'type': 'date', 'include_in_all': False},
                    'number_of_pages_filter': {'type': 'integer', 'include_in_all': False},
                    'tags': {
                        'type': 'nested',
                        'properties': {
                            'name': {'type': 'text', 'include_in_all': True},
                            'slug_filter': {'type': 'keyword', 'include_in_all': False},
                        },
                    }
                }
            }
        }

        self.assertDictEqual(mapping, expected_result)

    def test_get_document_id(self):
        # This must be tests_searchtest instead of 'tests_searchtest_tests_searchtestchild'
        # as it uses the contents base content type name.
        # This prevents the same object being accidentally indexed twice.
        self.assertEqual(self.es_mapping.get_document_id(self.obj), 'searchtests_book:' + str(self.obj.pk))

    def test_get_document(self):
        # Build document
        document = self.es_mapping.get_document(self.obj)

        # Sort partials
        if '_partials' in document:
            document['_partials'].sort()

        # Check
        expected_result = {
            # New
            'searchtests_novel__setting': "Middle Earth",
            'searchtests_novel__protagonist': {
                'name': "Frodo Baggins"
            },
            'searchtests_novel__characters': [
                {
                    'name': "Gandalf"
                },
                {
                    'name': "Bilbo Baggins"
                },
                {
                    'name': "Frodo Baggins"
                }
            ],

            # Changed
            'content_type': ["searchtests.Novel", "searchtests.Book"],
            '_partials': ['Middle Earth', 'The Fellowship of the Ring'],

            # Inherited
            'pk': '4',
            'title': 'The Fellowship of the Ring',
            'title_filter': 'The Fellowship of the Ring',
            'authors': [
                {
                    'name': 'J. R. R. Tolkien',
                    'date_of_birth_filter': datetime.date(1892, 1, 3)
                }
            ],
            'publication_date_filter': datetime.date(1954, 7, 29),
            'number_of_pages_filter': 423,
            'tags': []
        }

        self.assertDictEqual(document, expected_result)


class TestBackendConfiguration(TestCase):
    def test_default_settings(self):
        backend = Elasticsearch5SearchBackend(params={})

        self.assertEqual(len(backend.hosts), 1)
        self.assertEqual(backend.hosts[0]['host'], 'localhost')
        self.assertEqual(backend.hosts[0]['port'], 9200)
        self.assertEqual(backend.hosts[0]['use_ssl'], False)

    def test_hosts(self):
        # This tests that HOSTS goes to es_hosts
        backend = Elasticsearch5SearchBackend(params={
            'HOSTS': [
                {
                    'host': '127.0.0.1',
                    'port': 9300,
                    'use_ssl': True,
                    'verify_certs': True,
                }
            ]
        })

        self.assertEqual(len(backend.hosts), 1)
        self.assertEqual(backend.hosts[0]['host'], '127.0.0.1')
        self.assertEqual(backend.hosts[0]['port'], 9300)
        self.assertEqual(backend.hosts[0]['use_ssl'], True)

    def test_urls(self):
        # This test backwards compatibility with old URLS setting
        backend = Elasticsearch5SearchBackend(params={
            'URLS': [
                'http://localhost:12345',
                'https://127.0.0.1:54321',
                'http://username:password@elasticsearch.mysite.com',
                'https://elasticsearch.mysite.com/hello',
            ],
        })

        self.assertEqual(len(backend.hosts), 4)
        self.assertEqual(backend.hosts[0]['host'], 'localhost')
        self.assertEqual(backend.hosts[0]['port'], 12345)
        self.assertEqual(backend.hosts[0]['use_ssl'], False)

        self.assertEqual(backend.hosts[1]['host'], '127.0.0.1')
        self.assertEqual(backend.hosts[1]['port'], 54321)
        self.assertEqual(backend.hosts[1]['use_ssl'], True)

        self.assertEqual(backend.hosts[2]['host'], 'elasticsearch.mysite.com')
        self.assertEqual(backend.hosts[2]['port'], 80)
        self.assertEqual(backend.hosts[2]['use_ssl'], False)
        self.assertEqual(backend.hosts[2]['http_auth'], ('username', 'password'))

        self.assertEqual(backend.hosts[3]['host'], 'elasticsearch.mysite.com')
        self.assertEqual(backend.hosts[3]['port'], 443)
        self.assertEqual(backend.hosts[3]['use_ssl'], True)
        self.assertEqual(backend.hosts[3]['url_prefix'], '/hello')


@unittest.skipUnless(os.environ.get('ELASTICSEARCH_URL', False), "ELASTICSEARCH_URL not set")
@unittest.skipUnless(os.environ.get('ELASTICSEARCH_VERSION', '1') == '5', "ELASTICSEARCH_VERSION not set to 5")
class TestRebuilder(TestCase):
    def assertDictEqual(self, a, b):
        default = JSONSerializer().default
        self.assertEqual(
            json.dumps(a, sort_keys=True, default=default), json.dumps(b, sort_keys=True, default=default)
        )

    def setUp(self):
        self.backend = get_search_backend('elasticsearch')
        self.es = self.backend.es
        self.rebuilder = self.backend.get_rebuilder()

        self.backend.reset_index()

    def test_start_creates_index(self):
        # First, make sure the index is deleted
        try:
            self.es.indices.delete(self.backend.index_name)
        except self.NotFoundError:
            pass

        self.assertFalse(self.es.indices.exists(self.backend.index_name))

        # Run start
        self.rebuilder.start()

        # Check the index exists
        self.assertTrue(self.es.indices.exists(self.backend.index_name))

    def test_start_deletes_existing_index(self):
        # Put an alias into the index so we can check it was deleted
        self.es.indices.put_alias(name='this_index_should_be_deleted', index=self.backend.index_name)
        self.assertTrue(
            self.es.indices.exists_alias(name='this_index_should_be_deleted', index=self.backend.index_name)
        )

        # Run start
        self.rebuilder.start()

        # The alias should be gone (proving the index was deleted and recreated)
        self.assertFalse(
            self.es.indices.exists_alias(name='this_index_should_be_deleted', index=self.backend.index_name)
        )


@unittest.skipUnless(os.environ.get('ELASTICSEARCH_URL', False), "ELASTICSEARCH_URL not set")
@unittest.skipUnless(os.environ.get('ELASTICSEARCH_VERSION', '1') == '5', "ELASTICSEARCH_VERSION not set to 5")
class TestAtomicRebuilder(TestCase):
    def setUp(self):
        self.backend = get_search_backend('elasticsearch')
        self.backend.rebuilder_class = self.backend.atomic_rebuilder_class
        self.es = self.backend.es
        self.rebuilder = self.backend.get_rebuilder()

        self.backend.reset_index()

    def test_start_creates_new_index(self):
        # Rebuilder should make up a new index name that doesn't currently exist
        self.assertFalse(self.es.indices.exists(self.rebuilder.index.name))

        # Run start
        self.rebuilder.start()

        # Check the index exists
        self.assertTrue(self.es.indices.exists(self.rebuilder.index.name))

    def test_start_doesnt_delete_current_index(self):
        # Get current index name
        current_index_name = list(self.es.indices.get_alias(name=self.rebuilder.alias.name).keys())[0]

        # Run start
        self.rebuilder.start()

        # The index should still exist
        self.assertTrue(self.es.indices.exists(current_index_name))

        # And the alias should still point to it
        self.assertTrue(self.es.indices.exists_alias(name=self.rebuilder.alias.name, index=current_index_name))

    def test_finish_updates_alias(self):
        # Run start
        self.rebuilder.start()

        # Check that the alias doesn't point to new index
        self.assertFalse(
            self.es.indices.exists_alias(name=self.rebuilder.alias.name, index=self.rebuilder.index.name)
        )

        # Run finish
        self.rebuilder.finish()

        # Check that the alias now points to the new index
        self.assertTrue(self.es.indices.exists_alias(name=self.rebuilder.alias.name, index=self.rebuilder.index.name))

    def test_finish_deletes_old_index(self):
        # Get current index name
        current_index_name = list(self.es.indices.get_alias(name=self.rebuilder.alias.name).keys())[0]

        # Run start
        self.rebuilder.start()

        # Index should still exist
        self.assertTrue(self.es.indices.exists(current_index_name))

        # Run finish
        self.rebuilder.finish()

        # Index should be gone
        self.assertFalse(self.es.indices.exists(current_index_name))
