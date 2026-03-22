// Operative1 Background Service Worker
// Handles Twitter posting via GraphQL from the browser context

const TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA";
const FALLBACK_QUERY_ID = "7TKRKCPuAGsmYde0CudbVg";

// Dynamic queryId cache
let cachedQueryId = null;
let queryIdFetchedAt = 0;
const QUERY_ID_MAX_AGE_MS = 60 * 60 * 1000; // 1 hour

async function fetchCreateTweetQueryId() {
  try {
    console.log('[Operative1] Fetching fresh CreateTweet queryId from x.com...');

    // Step 1: Fetch x.com homepage to find the main JS bundle
    const homeRes = await fetch('https://x.com', { credentials: 'include' });
    const homeHtml = await homeRes.text();

    // Find main JS bundle URLs — look for client-web bundles
    const scriptMatches = [...homeHtml.matchAll(/src="(https:\/\/abs\.twimg\.com\/responsive-web\/client-web[^"]+\.js)"/g)];
    if (scriptMatches.length === 0) {
      console.log('[Operative1] No client-web JS bundles found in HTML');
      return null;
    }

    console.log('[Operative1] Found', scriptMatches.length, 'client-web bundles, checking for CreateTweet...');

    // Step 2: Check each bundle for CreateTweet queryId
    for (const match of scriptMatches) {
      const bundleUrl = match[1];
      try {
        const bundleRes = await fetch(bundleUrl);
        const bundleJs = await bundleRes.text();

        // Try multiple regex patterns since Twitter's bundler changes formats
        const patterns = [
          /queryId:"([^"]+)"[^}]*operationName:"CreateTweet"/,
          /CreateTweet[^{]*\{[^}]*queryId:"([^"]+)"/,
          /"CreateTweet"[^}]*queryId:"([^"]+)"/,
          /operationName:"CreateTweet"[^}]*queryId:"([^"]+)"/,
        ];

        for (const pattern of patterns) {
          const idMatch = bundleJs.match(pattern);
          if (idMatch) {
            console.log('[Operative1] Found CreateTweet queryId:', idMatch[1], 'in bundle:', bundleUrl.split('/').pop());
            return idMatch[1];
          }
        }
      } catch (bundleErr) {
        console.log('[Operative1] Failed to fetch bundle:', bundleUrl.split('/').pop(), bundleErr.message);
      }
    }

    console.log('[Operative1] CreateTweet queryId not found in any bundle');
    return null;
  } catch (e) {
    console.log('[Operative1] Error fetching queryId:', e.message);
    return null;
  }
}

async function getQueryId(forceRefresh = false) {
  const age = Date.now() - queryIdFetchedAt;
  if (!forceRefresh && cachedQueryId && age < QUERY_ID_MAX_AGE_MS) {
    console.log('[Operative1] Using cached queryId:', cachedQueryId, '(age:', Math.round(age / 1000), 's)');
    return cachedQueryId;
  }

  const freshId = await fetchCreateTweetQueryId();
  if (freshId) {
    cachedQueryId = freshId;
    queryIdFetchedAt = Date.now();
    return freshId;
  }

  // Fall back to cached or hardcoded
  if (cachedQueryId) {
    console.log('[Operative1] Fresh fetch failed, using cached queryId:', cachedQueryId);
    return cachedQueryId;
  }
  console.log('[Operative1] Fresh fetch failed, using fallback queryId:', FALLBACK_QUERY_ID);
  return FALLBACK_QUERY_ID;
}

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

function buildTweetPayload(text, replyToTweetId, mediaIds = [], queryId = FALLBACK_QUERY_ID) {
  const variables = {
    tweet_text: text,
    dark_request: false,
    media: {
      media_entities: mediaIds.map(id => ({ media_id: id, tagged_users: [] })),
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
    queryId
  };
}

async function postTweet(text, replyToTweetId, mediaIds = [], passedCookies = null, _retried = false) {
  console.log('[Operative1] postTweet called');
  console.log('[Operative1] Reply to tweet ID:', replyToTweetId);
  console.log('[Operative1] Tweet text:', text);
  console.log('[Operative1] Media IDs:', mediaIds);
  console.log('[Operative1] Using passed cookies:', passedCookies ? 'yes' : 'no (falling back to browser)');

  // Always prefer fresh browser cookies (ct0 rotates frequently)
  // Fall back to passed/stored cookies only if browser cookies unavailable
  const browserCookies = await getTwitterCookies();
  const cookies = browserCookies || passedCookies;
  console.log('[Operative1] Cookie source:', browserCookies ? 'browser (fresh)' : passedCookies ? 'passed (stored)' : 'none');

  if (!cookies) {
    console.log('[Operative1] ERROR: No cookies found');
    return { success: false, error: 'Not logged into Twitter. Please log in at x.com first.' };
  }

  // Get dynamic queryId
  const queryId = await getQueryId();
  const graphqlUrl = `https://x.com/i/api/graphql/${queryId}/CreateTweet`;

  const headers = {
    'authorization': `Bearer ${TWITTER_BEARER}`,
    'x-csrf-token': cookies.ct0,
    'content-type': 'application/json',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-active-user': 'yes',
    'x-twitter-client-language': 'en'
  };

  const payload = buildTweetPayload(text, replyToTweetId, mediaIds, queryId);

  console.log('[Operative1] Request URL:', graphqlUrl);
  console.log('[Operative1] Using queryId:', queryId);
  console.log('[Operative1] Request payload:', JSON.stringify(payload, null, 2));

  try {
    const response = await fetch(graphqlUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      credentials: 'include'
    });

    console.log('[Operative1] Response status:', response.status);

    const responseText = await response.text();
    console.log('[Operative1] Raw response body:', responseText.slice(0, 500));

    let data;
    try {
      data = JSON.parse(responseText);
    } catch (parseErr) {
      console.log('[Operative1] ERROR: Failed to parse response as JSON:', parseErr.message);
      return { success: false, error: `Invalid JSON response: ${responseText.slice(0, 200)}` };
    }

    if (response.status === 200) {
      // Check for errors array first
      if (data.errors && data.errors.length > 0) {
        const errorMsg = data.errors[0].message || JSON.stringify(data.errors[0]);
        console.log('[Operative1] ERROR: GraphQL errors:', errorMsg);

        // Retry with fresh queryId if this looks like a stale queryId error
        if (!_retried && (errorMsg.includes('not found') || errorMsg.includes('query'))) {
          console.log('[Operative1] Possible stale queryId, refreshing and retrying...');
          cachedQueryId = null;
          return postTweet(text, replyToTweetId, mediaIds, passedCookies, true);
        }

        return { success: false, error: `Twitter error: ${errorMsg}` };
      }

      // Check for tweet result
      const tweetResult = data?.data?.create_tweet?.tweet_results?.result;
      const tweetId = tweetResult?.rest_id;

      if (tweetId) {
        console.log('[Operative1] SUCCESS: Tweet posted with ID:', tweetId);
        return { success: true, tweet_id: tweetId };
      } else {
        console.log('[Operative1] ERROR: No tweet ID found. Full data:', JSON.stringify(data, null, 2));
        return { success: false, error: 'Tweet may have posted but could not confirm ID. Check console for details.' };
      }
    } else if (response.status === 400 || response.status === 404) {
      // Bad request or not found — likely stale queryId
      if (!_retried) {
        console.log('[Operative1] Got', response.status, '— refreshing queryId and retrying...');
        cachedQueryId = null;
        return postTweet(text, replyToTweetId, mediaIds, passedCookies, true);
      }
      console.log('[Operative1] ERROR: Still got', response.status, 'after queryId refresh:', responseText.slice(0, 300));
      return { success: false, error: `Twitter returned status ${response.status}: ${responseText.slice(0, 200)}` };
    } else if (response.status === 403) {
      if (responseText.toLowerCase().includes('ct0') || responseText.toLowerCase().includes('csrf')) {
        return { success: false, error: 'Twitter session expired. Please refresh x.com and try again.' };
      }
      console.log('[Operative1] ERROR: 403 Forbidden:', responseText.slice(0, 300));
      return { success: false, error: `Twitter rejected: ${responseText.slice(0, 200)}` };
    } else if (response.status === 401) {
      return { success: false, error: 'Twitter authentication failed. Please log in at x.com.' };
    } else {
      console.log('[Operative1] ERROR: Unexpected status', response.status, responseText.slice(0, 300));
      return { success: false, error: `Twitter returned status ${response.status}: ${responseText.slice(0, 200)}` };
    }
  } catch (e) {
    console.log('[Operative1] ERROR: Network/fetch error:', e.message, e.stack);
    return { success: false, error: `Network error: ${e.message}` };
  }
}

// Upload image to Twitter and get media_id
// Uses the chunked upload API: INIT -> APPEND -> FINALIZE
async function uploadMediaToTwitter(imageUrl, cookies) {
  console.log('[Operative1] Starting media upload for:', imageUrl);

  // Fetch the image from the URL
  const imageResponse = await fetch(imageUrl);
  if (!imageResponse.ok) {
    throw new Error(`Failed to fetch image: ${imageResponse.status}`);
  }

  const imageBlob = await imageResponse.blob();
  const imageBuffer = await imageBlob.arrayBuffer();
  const imageBytes = new Uint8Array(imageBuffer);

  console.log('[Operative1] Image fetched, size:', imageBytes.length, 'type:', imageBlob.type);

  const headers = {
    'authorization': `Bearer ${TWITTER_BEARER}`,
    'x-csrf-token': cookies.ct0,
  };

  // Step 1: INIT
  const initFormData = new FormData();
  initFormData.append('command', 'INIT');
  initFormData.append('total_bytes', imageBytes.length.toString());
  initFormData.append('media_type', imageBlob.type || 'image/jpeg');
  initFormData.append('media_category', 'tweet_image');

  const initResponse = await fetch('https://upload.twitter.com/i/media/upload.json', {
    method: 'POST',
    headers,
    body: initFormData,
    credentials: 'include'
  });

  if (!initResponse.ok) {
    const errorText = await initResponse.text();
    console.log('[Operative1] INIT failed:', errorText);
    throw new Error(`Media INIT failed: ${initResponse.status}`);
  }

  const initData = await initResponse.json();
  const mediaId = initData.media_id_string;
  console.log('[Operative1] INIT success, media_id:', mediaId);

  // Step 2: APPEND (single chunk for images under 5MB)
  const appendFormData = new FormData();
  appendFormData.append('command', 'APPEND');
  appendFormData.append('media_id', mediaId);
  appendFormData.append('segment_index', '0');
  appendFormData.append('media', new Blob([imageBytes], { type: imageBlob.type }));

  const appendResponse = await fetch('https://upload.twitter.com/i/media/upload.json', {
    method: 'POST',
    headers,
    body: appendFormData,
    credentials: 'include'
  });

  if (!appendResponse.ok) {
    const errorText = await appendResponse.text();
    console.log('[Operative1] APPEND failed:', errorText);
    throw new Error(`Media APPEND failed: ${appendResponse.status}`);
  }

  console.log('[Operative1] APPEND success');

  // Step 3: FINALIZE
  const finalizeFormData = new FormData();
  finalizeFormData.append('command', 'FINALIZE');
  finalizeFormData.append('media_id', mediaId);

  const finalizeResponse = await fetch('https://upload.twitter.com/i/media/upload.json', {
    method: 'POST',
    headers,
    body: finalizeFormData,
    credentials: 'include'
  });

  if (!finalizeResponse.ok) {
    const errorText = await finalizeResponse.text();
    console.log('[Operative1] FINALIZE failed:', errorText);
    throw new Error(`Media FINALIZE failed: ${finalizeResponse.status}`);
  }

  const finalizeData = await finalizeResponse.json();
  console.log('[Operative1] FINALIZE success:', JSON.stringify(finalizeData));

  return mediaId;
}

// Listen for messages from the Operative1 dashboard
chrome.runtime.onMessageExternal.addListener((request, sender, sendResponse) => {
  const action = request.action || request.type;
  console.log('[Operative1] Received message:', action, 'from:', sender.origin);

  if (action === 'ping') {
    console.log('[Operative1] Ping received, responding with version 1.6.0');
    sendResponse({ success: true, version: '1.6.0' });
    return true;
  }

  if (action === 'post_reply') {
    const { tweet_id, reply_text, auth_token, ct0 } = request;
    console.log('[Operative1] post_reply request:', { tweet_id, reply_text: reply_text?.slice(0, 50) + '...', has_stored_cookies: !!(auth_token && ct0) });

    if (!tweet_id || !reply_text) {
      console.log('[Operative1] ERROR: Missing tweet_id or reply_text');
      sendResponse({ success: false, error: 'Missing tweet_id or reply_text' });
      return true;
    }

    // Use passed cookies (from stored DB credentials) if available, otherwise fall back to browser cookies
    const passedCookies = (auth_token && ct0) ? { auth_token, ct0 } : null;

    postTweet(reply_text, tweet_id, [], passedCookies)
      .then(result => {
        console.log('[Operative1] postTweet result:', JSON.stringify(result));
        sendResponse(result);
      })
      .catch(e => {
        console.log('[Operative1] postTweet exception:', e.message, e.stack);
        sendResponse({ success: false, error: e.message });
      });

    return true; // Keep channel open for async response
  }

  // NEW: Handle broadcast posts (standalone tweets, optionally with media)
  if (action === 'post_broadcast') {
    const { content, media_url, auth_token, ct0 } = request;
    console.log('[Operative1] post_broadcast request:', { content: content?.slice(0, 50) + '...', media_url: media_url ? 'yes' : 'no', has_stored_cookies: !!(auth_token && ct0) });

    if (!content) {
      console.log('[Operative1] ERROR: Missing content');
      sendResponse({ success: false, error: 'Missing content' });
      return true;
    }

    (async () => {
      try {
        // Use passed cookies (from stored DB credentials) if available, otherwise fall back to browser cookies
        const cookies = (auth_token && ct0) ? { auth_token, ct0 } : await getTwitterCookies();
        if (!cookies) {
          sendResponse({ success: false, error: 'Not logged into Twitter. Please log in at x.com first.' });
          return;
        }

        let mediaIds = [];

        // Upload media if provided
        if (media_url) {
          try {
            const mediaId = await uploadMediaToTwitter(media_url, cookies);
            mediaIds.push(mediaId);
            console.log('[Operative1] Media uploaded successfully:', mediaId);
          } catch (mediaError) {
            console.log('[Operative1] Media upload failed:', mediaError.message);
            // Ask user if they want to continue without media
            sendResponse({
              success: false,
              error: `Media upload failed: ${mediaError.message}. The tweet was not posted.`,
              media_failed: true
            });
            return;
          }
        }

        // Post the tweet (no replyToTweetId for broadcasts)
        const passedCookies = (auth_token && ct0) ? { auth_token, ct0 } : null;
        const result = await postTweet(content, null, mediaIds, passedCookies);
        console.log('[Operative1] post_broadcast result:', JSON.stringify(result));
        sendResponse(result);

      } catch (e) {
        console.log('[Operative1] post_broadcast exception:', e.message, e.stack);
        sendResponse({ success: false, error: e.message });
      }
    })();

    return true; // Keep channel open for async response
  }

  if (action === 'check_login') {
    getTwitterCookies()
      .then(cookies => sendResponse({ logged_in: !!cookies }))
      .catch(() => sendResponse({ logged_in: false }));
    return true;
  }

  console.log('[Operative1] Unknown action:', action);
  sendResponse({ success: false, error: 'Unknown action' });
  return true;
});

console.log('[Operative1] Background service worker loaded, version 1.6.0 (dynamic queryId)');
