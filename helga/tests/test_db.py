from unittest.mock import Mock, patch

from pymongo.errors import ConnectionFailure

from helga import db


@patch("helga.db.MongoClient")
@patch("helga.db.settings")
def test_connect_returns_none_on_failure(settings, mongo):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "DB": "baz",
    }

    mongo.side_effect = ConnectionFailure
    assert db.connect() == (None, None)


@patch("helga.db.MongoClient")
@patch("helga.db.settings")
def test_connect_authenticates(settings, mongo):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "USERNAME": "foo",
        "PASSWORD": "bar",
        "DB": "baz",
    }

    mongo.return_value = mongo

    database = Mock()
    mongo.__getitem__ = Mock()
    mongo.__getitem__.return_value = database

    db.connect()
    mongo.assert_called_with("mongodb://foo:bar@localhost:1234/baz?authSource=baz")


@patch("helga.db.MongoClient")
@patch("helga.db.settings")
def test_connect_url_encodes_credentials(settings, mongo):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "USERNAME": "foo@domain",
        "PASSWORD": "bar/baz",
        "DB": "qux",
    }

    mongo.return_value = mongo
    mongo.__getitem__ = Mock()
    mongo.__getitem__.return_value = Mock()

    db.connect()
    mongo.assert_called_with("mongodb://foo%40domain:bar%2Fbaz@localhost:1234/qux?authSource=qux")


@patch("helga.db.MongoClient")
@patch("helga.db.settings")
def test_connect(settings, mongo):
    settings.DATABASE = {
        "HOST": "localhost",
        "PORT": "1234",
        "DB": "baz",
    }

    mongo.return_value = mongo

    database = Mock()
    mongo.__getitem__ = Mock()
    mongo.__getitem__.return_value = database

    assert db.connect() == (mongo, database)
    mongo.assert_called_with("mongodb://localhost:1234/baz")
    mongo.__getitem__.assert_called_with("baz")
