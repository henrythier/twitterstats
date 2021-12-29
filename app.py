import json
import os
import re
from typing import ParamSpec
from flask import Flask, render_template, redirect, url_for
from flask_restful import Resource, Api, reqparse
import pandas as pd
import requests
from dateutil import parser


app = Flask(__name__, static_url_path='',
            static_folder='static',
            template_folder='template')
api = Api(app)


BEARER = os.getenv("TWITTER_BEARER")
BEARER = "AAAAAAAAAAAAAAAAAAAAAMgXXgEAAAAAsPs%2BsYjYHga2srwskxUNrVB8SWc%3DdR9s4KlBNHacRi1CmVti99KSvWw9cXok4g0KzTu1AeLBFF7uDf"


def bearer_oauth(r):
    r.headers["Authorization"] = f"Bearer {BEARER}"
    return r


def get_user(username):
    params = {'user.fields': 'profile_image_url'}
    url = f'https://api.twitter.com/2/users/by/username/{username}?'
    r = requests.get(url, auth=bearer_oauth, params=params)
    if r.status_code != 200:
        raise Exception(f'Request returned an error: {r.status_code} {r.text}')
    return r.json()['data']


def get_tweets(userid, params):
    params['expansions'] = 'author_id'
    params['user.fields'] = 'username'
    params['tweet.fields'] = 'created_at,in_reply_to_user_id'
    url = f'https://api.twitter.com/2/users/{userid}/liked_tweets'
    # url = 'https://api.twitter.com/1.1/favorites/list.json?'
    r = requests.get(url, auth=bearer_oauth, params=params)
    return r.json(), r.status_code


def process_tweet(tweet):
    ''' function to reduce tweets to relevant data '''
    tweet = {
        'created_at': parser.parse(tweet['created_at']),
        'id': tweet['id'],
        'reply_to': tweet.get('in_reply_to_user_id'),
        'author_id': tweet['author_id']
    }
    return tweet


def calc_stats(user, tweets, users):
    num_likes = len(tweets)
    num_accounts = len(tweets['author_id'].unique())
    num_liked_replies = len(tweets[tweets['reply_to'] == user['id']])
    share_liked_replies = num_liked_replies / num_likes * 100
    first_like = tweets['created_at'].iloc[-1]
    last_like = tweets['created_at'].iloc[0]

    top_five = {users[k]: v for k, v in dict(tweets['author_id'].value_counts().head(5)).items()}

    stats = {
        'user': user['username'],
        'num_likes': num_likes,
        'num_accounts': num_accounts,
        'num_liked_replies': num_liked_replies,
        'share_liked_replies': f"{share_liked_replies:.2f}%",
        'top_five': top_five,
        'first_like': f"{first_like:%Y-%m-%d}",
        'last_like': f"{last_like:%Y-%m-%d}"
    }
    return stats


def get_like_stats(username):
    try:
        user = get_user(username)
    except Exception as e:
        return None, 403

    # setup
    parameters = {}
    likes = []
    users = {}
    i = 0
    status = 200

    while True:
        raw_data, status_code = get_tweets(user['id'], parameters)

        if i > 0 and status_code == 429:
            status = status_code
            break

        # check for errors
        if 'errors' in raw_data:
            return None, 403

        # check if account has likes
        if i == 0 and len(raw_data) == 0:
            return None, 404

        likes_batch = raw_data.get('data')
        if not likes_batch:
            break
        likes_batch = [process_tweet(tweet) for tweet in likes_batch if tweet['created_at'][:4] == '2021']
        if len(likes_batch) == 0:
            break

        likes.extend(likes_batch)

        user_batch = {user['id']: user['username'] for user in raw_data['includes']['users']}
        users.update(user_batch)

        next_token = raw_data.get('meta', {}).get('next_token')
        if next_token:
            parameters['pagination_token'] = next_token
        else:
            break

        i += 1
        #print(f'{i = }, {len(likes) = }')
    
    likes = pd.DataFrame.from_dict(likes)
    stats = calc_stats(user, likes, users)

    return stats, status


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/<name>")
def user(name):
    regexp = re.compile(r'^\w{1,15}$')
    if regexp.search(name):
        data, status = get_like_stats(name)
        if status in (200, 429):
            return render_template('user.html', name=name, data=data)
        elif status == 403:
            return render_template('404.html', name=name)
    return render_template('error.html', name=name)


if __name__ == '__main__':
    app.run()  # run our Flask app
