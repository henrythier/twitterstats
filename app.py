from flask import Flask
from flask import render_template, redirect, url_for
from flask_restful import Resource, Api, reqparse
import pandas as pd
import ast
import json
import requests
from dateutil import parser

app = Flask(__name__, static_url_path='',
            static_folder='static',
            template_folder='template')
app.config["DEBUG"] = True
api = Api(app)

'''
Start: Twitter functions
'''
# authentication
with open('api_keys.json') as f:
  data = json.load(f)
  bearer = data["bearer"]

# request parameters
count = 200
parameters = {'count': count}

# year
relevant_year = 2021

# relevant data
relevant_data_keys = ['created_at', 'id', 'text', 'in_reply_to_screen_name']

# twitter end point
url = "https://api.twitter.com/1.1/favorites/list.json?"

# set up headers
headers = {"Accept": "application/json", "Authorization": f"Bearer {bearer}"}

# liked tweets list
liked_tweets = list()

# get liked tweets
def get_dict_of_tweets(parameters):
  resp = requests.get(url, headers=headers, params=parameters)
  tweet_dict_raw = resp.json()
  return tweet_dict_raw

# function to reduce twitters original response to relevant data
def get_relevant_info(response_dict):
  reduced_dict = {rel_key: response_dict[rel_key] for rel_key in relevant_data_keys}
  reduced_dict['created_at'] = parser.parse(reduced_dict['created_at'])
  reduced_dict['user'] = response_dict['user']['screen_name']
  reduced_dict['tweet_url'] = f"twitter.com/{reduced_dict['user']}/status/{reduced_dict['id']}"
  return reduced_dict

# function to turn reduced dict into dataframe and remove older likes
def tweets_to_df(liked_tweets):
  # move dict into dataframe
  df = pd.DataFrame.from_dict(liked_tweets)

  # only keep tweets from year in question
  df_years = df['created_at'].apply(lambda x: x.year)
  df = df[df_years == relevant_year]
  return df

# function to calculate and print stats
def calc_and_print_stats(df, screen_name):
  # number of likes
  num_of_tweets = len(df)
  date_of_first_tweet = df['created_at'].iloc[-1].strftime("%d %B %Y")

  # number of liked accounts
  num_of_different_accounts = len(df['user'].unique())

  # number of liked replys
  num_of_liked_replys = len(df.loc[df['in_reply_to_screen_name'] == screen_name])
  per_liked_replys = num_of_liked_replys / num_of_tweets * 100

  # top 10 accounts
  top_ten = df['user'].value_counts().head(10)
  stats = {'user': parameters['screen_name'],
           'num_of_likes': num_of_tweets,
           'num_of_different_accounts': num_of_different_accounts,
           'num_of_liked_replys': num_of_liked_replys,
           'per_liked_replys': per_liked_replys,
           'top_ten': top_ten.to_dict()}
  return stats

def get_like_stats(screen_name):
  # setup
  parameters.pop("max_id", None)
  parameters['screen_name'] = screen_name
  liked_tweets = list()
  iteration_count = 0
  in_relevant_year = True

  # loop while still in relevant year
  while in_relevant_year:

    # get tweets
    tweet_dict_raw = get_dict_of_tweets(parameters)

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

    # check if still in relevant year
    year_of_last_tweet = liked_tweets[-1]['created_at'].year
    in_relevant_year = year_of_last_tweet >= relevant_year

    # update parameters
    parameters['max_id'] = batch_of_liked_tweets[-1]['id'] - 1
    iteration_count += 1

  df = tweets_to_df(liked_tweets)
  response = calc_and_print_stats(df, screen_name)
  return response, 200
'''
End: Twitter functions
'''

@app.route("/<name>")
def user(name):
    print(name)
    data, status = get_like_stats(name)
    return {'status': status, 'data': data}, 200

if __name__ == '__main__':
    app.run()  # run our Flask app
