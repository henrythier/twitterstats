import os
from flask import Flask, render_template, redirect, url_for
from flask_restful import Resource, Api, reqparse
import pandas as pd
import requests
from dateutil import parser
import os

app = Flask(__name__, static_url_path='',
            static_folder='static',
            template_folder='template')
api = Api(app)

# To set your enviornment variables in your terminal run the following line:
bearer_token = os.getenv("TWITTER_BEARER")

'''
Start: Twitter functions
'''


# year
relevant_year = 2021


def get_user(username):
    user_fields = "user.fields=profile_image_url"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    url = f'https://api.twitter.com/2/users/by?usernames={username}&{user_fields}'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception(f'Request returned an error: {r.status_code} {r.text}')
    return r.json()


def get_tweets(username, max_id):
    headers = {"Authorization": f"Bearer {bearer_token}"}
    url = f'https://api.twitter.com/1.1/favorites/list.json?screen_name={username}&count=200&max_id={max_id}'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise Exception(f'Request returned an error: {r.status_code} {r.text}')
    return r.json()


def get_relevant_info(response_dict):
    ''' function to reduce twitters original response to relevant data '''
    relevant_data_keys = ['created_at', 'id', 'text', 'in_reply_to_screen_name']
    reduced_dict = {rel_key: response_dict[rel_key] for rel_key in relevant_data_keys}
    reduced_dict['created_at'] = parser.parse(reduced_dict['created_at'])
    reduced_dict['user'] = response_dict['user']['screen_name']
    reduced_dict['tweet_url'] = f"twitter.com/{reduced_dict['user']}/status/{reduced_dict['id']}"
    return reduced_dict


def tweets_to_df(liked_tweets):
    ''' function to turn reduced dict into dataframe and remove older likes '''
    # move dict into dataframe
    df = pd.DataFrame.from_dict(liked_tweets)

    # only keep tweets from year in question
    df_years = df['created_at'].apply(lambda x: x.year)
    df = df[df_years == relevant_year]
    return df


def calc_and_print_stats(df, screen_name):
    ''' function to calculate stats '''
    # number of likes
    num_of_tweets = len(df)

    # number of liked accounts
    num_of_different_accounts = len(df['user'].unique())

    # number of liked replys
    num_of_liked_replys = len(df.loc[df['in_reply_to_screen_name'] == screen_name])
    per_liked_replys = num_of_liked_replys / num_of_tweets * 100

    # top 10 accounts
    top_ten = df['user'].value_counts().head(10)
    stats = {'user': screen_name,
             'num_of_likes': num_of_tweets,
             'num_of_different_accounts': num_of_different_accounts,
             'num_of_liked_replys': num_of_liked_replys,
             'per_liked_replys': per_liked_replys,
             'top_ten': top_ten.to_dict(),
             'first_like': df['created_at'].iloc[-1],
             'last_like': df['created_at'].iloc[0]}
    return stats


def get_like_stats(screen_name):
    # setup
    liked_tweets = list()
    iteration_count = 0
    max_id = None

    # loop while still in relevant year
    while True:

        # get tweets
        tweet_dict_raw = get_tweets(screen_name, max_id)

        # check for errors
        if 'errors' in tweet_dict_raw:
            return None, 403

        # check if account has likes
        if iteration_count == 0 and len(tweet_dict_raw) == 0:
            return None, 404

        batch_of_liked_tweets = [get_relevant_info(tweet) for tweet in tweet_dict_raw]

        # maximum number of likes retrieved for user
        if len(batch_of_liked_tweets) <= 1 and iteration_count > 0:
            print(f'End of likes after {iteration_count} requests')
            break

        # append to list of liked tweets
        liked_tweets.extend(batch_of_liked_tweets)

        # update parameters
        max_id = batch_of_liked_tweets[-1]['id'] - 1
        iteration_count += 1

        # check if still in relevant year
        if relevant_year > liked_tweets[-1]['created_at'].year:
            break

    df = tweets_to_df(liked_tweets)
    response = calc_and_print_stats(df, screen_name)
    return response, 200


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/<name>")
def user(name):
    data, status = get_like_stats(name)
    if status == 200:
        return render_template('user.html', name=name, data=data)
    elif status == 403:
        return render_template('404.html', name=name)
    else:
        return render_template('error.html', name=name)


if __name__ == '__main__':
    app.run()  # run our Flask app
