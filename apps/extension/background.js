// Operative1 Background Service Worker
// Handles Twitter posting via GraphQL from the browser context

const TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA";
const GRAPHQL_QUERY_ID = "7TKRKCPuAGsmYde0CudbVg";
const GRAPHQL_CREATE_TWEET_URL = `https://x.com/i/api/graphql/${GRAPHQL_QUERY_ID}/CreateTweet`;

async function getTwitterCookies() {
  return new Promise((resolve) => {
    const cookies = {};
    let pending = 2;

    function checkDone() {
      pending--;
      if (pending === 0) {
        resolve(cookies.auth_token && cookies.ct0 ? cookies : null);
      }
    }

    chrome.cookies.get({ url: 'https://x.com', name: 'auth_token' }, (cookie) => {
      if (cookie) cookies.auth_token = cookie.value;
      checkDone();
    });

    chrome.cookies.get({ url: 'https://x.com', name: 'ct0' }, (cookie) => {
      if (cookie) cookies.ct0 = cookie.value;
      checkDone();
    });
  });
}

function buildTweetPayload(text, replyToTweetId) {
  const variables = {
    tweet_text: text,
    dark_request: false,
    media: {
      media_entities: [],
      possibly_sensitive: false
    },
    semantic_annotation_ids: []
  };

  if (replyToTweetId) {
    variables.reply = {
      in_reply_to_tweet_id: String(replyToTweetId),
      exclude_reply_user_ids: []
    };
  }

  const features = {
    communities_web_enable_tweet_community_results_fetch: true,
    c9s_tweet_anatomy_moderator_badge_enabled: true,
    tweetypie_unmention_optimization_enabled: true,
    responsive_web_edit_tweet_api_enabled: true,
    graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
    view_counts_everywhere_api_enabled: true,
    longform_notetweets_consumption_enabled: true,
    responsive_web_twitter_article_tweet_consumption_enabled: true,
    tweet_awards_web_tipping_enabled: false,
    creator_subscriptions_quote_tweet_preview_enabled: false,
    longform_notetweets_rich_text_read_enabled: true,
    longform_notetweets_inline_media_enabled: true,
    articles_preview_enabled: true,
    rweb_video_timestamps_enabled: true,
    rweb_tipjar_consumption_enabled: true,
    responsive_web_graphql_exclude_directive_enabled: true,
    verified_phone_label_enabled: false,
    freedom_of_speech_not_reach_fetch_enabled: true,
    standardized_nudges_misinfo: true,
    tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
    responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
    responsive_web_graphql_timeline_navigation_enabled: true,
    responsive_web_enhance_cards_enabled: false
  };

  return {
    variables,
    features,
    queryId: GRAPHQL_QUERY_ID
  };
}

async function postTweet(text, replyToTweetId) {
  const cookies = await getTwitterCookies();

  if (!cookies) {
    return { success: false, error: 'Not logged into Twitter. Please log in at x.com first.' };
  }

  const headers = {
    'authorization': `Bearer ${TWITTER_BEARER}`,
    'x-csrf-token': cookies.ct0,
    'content-type': 'application/json',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-active-user': 'yes',
    'x-twitter-client-language': 'en'
  };

  const payload = buildTweetPayload(text, replyToTweetId);

  try {
    const response = await fetch(GRAPHQL_CREATE_TWEET_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      credentials: 'include'
    });

    if (response.status === 200) {
      const data = await response.json();
      const tweetResult = data?.data?.create_tweet?.tweet_results?.result;
      const tweetId = tweetResult?.rest_id;

      if (tweetId) {
        return { success: true, tweet_id: tweetId };
      } else {
        return { success: false, error: 'Tweet may have posted but could not confirm ID' };
      }
    } else if (response.status === 403) {
      const errorText = await response.text();
      if (errorText.toLowerCase().includes('ct0') || errorText.toLowerCase().includes('csrf')) {
        return { success: false, error: 'Twitter session expired. Please refresh x.com and try again.' };
      }
      return { success: false, error: `Twitter rejected the request: ${errorText.slice(0, 200)}` };
    } else if (response.status === 401) {
      return { success: false, error: 'Twitter authentication failed. Please log in at x.com.' };
    } else {
      const errorText = await response.text();
      return { success: false, error: `Twitter returned status ${response.status}: ${errorText.slice(0, 200)}` };
    }
  } catch (e) {
    return { success: false, error: `Network error: ${e.message}` };
  }
}

// Listen for messages from the Operative1 dashboard
chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  const action = request.action || request.type;

  if (action === 'ping') {
    sendResponse({ success: true, version: '1.1.1' });
    return true;
  }

  if (action === 'post_reply') {
    const { tweet_id, reply_text } = request;

    if (!tweet_id || !reply_text) {
      sendResponse({ success: false, error: 'Missing tweet_id or reply_text' });
      return true;
    }

    postTweet(reply_text, tweet_id)
      .then(result => sendResponse(result))
      .catch(e => sendResponse({ success: false, error: e.message }));

    return true; // Keep channel open for async response
  }

  if (action === 'check_login') {
    getTwitterCookies()
      .then(cookies => sendResponse({ logged_in: !!cookies }))
      .catch(() => sendResponse({ logged_in: false }));
    return true;
  }

  sendResponse({ success: false, error: 'Unknown action' });
  return true;
});
