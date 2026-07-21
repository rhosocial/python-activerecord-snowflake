# tests/rhosocial/activerecord_snowflake_test/feature/query/snowflake/test_json_queries.py
"""
Snowflake JSON query tests.

Snowflake has JSON functions but uses LONGTEXT for JSON columns for
compatibility with other backends that don't support native JSON.
This tests uses TEXT storage with json.dumps/json.loads serialization.
"""
import json

import pytest

from rhosocial.activerecord.testsuite.utils import requires_json_operations


@pytest.mark.snowflake_json
@requires_json_operations()
def test_snowflake_json_text_operations(json_user_fixture):
    """
    Test JSON operations using TEXT storage in Snowflake.

    Snowflake supports JSON functions, but to maintain compatibility with
    backends that don't have native JSON support, this test stores
    JSON as TEXT and uses application-level serialization.
    """
    JsonUser = json_user_fixture

    user_data = {
        'preferences': {
            'theme': 'dark',
            'language': 'en',
            'notifications': True
        },
        'settings': {
            'privacy': 'public',
            'timezone': 'UTC'
        },
        'tags': ['developer', 'python', 'activerecord']
    }

    json_user = JsonUser(
        username='json_test_user',
        email='json@example.com',
        age=28,
        settings=json.dumps(user_data['settings']),
        tags=json.dumps(user_data['tags']),
        profile=json.dumps(user_data['preferences'])
    )
    json_user.save()

    results = JsonUser.query().where(JsonUser.c.username == 'json_test_user').all()
    assert len(results) == 1
    assert results[0].username == 'json_test_user'

    retrieved_settings = json.loads(results[0].settings)
    assert retrieved_settings['privacy'] == 'public'
    assert retrieved_settings['timezone'] == 'UTC'

    retrieved_tags = json.loads(results[0].tags)
    assert 'developer' in retrieved_tags
    assert 'python' in retrieved_tags