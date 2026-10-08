// Netlify Function: proxy for Foursquare Places API
// places-api.foursquare.com blocks browser CORS, so we proxy server-side.
// The browser passes its locally-stored API key via X-FSQ-Key header.

exports.handler = async (event) => {
  // Handle CORS preflight
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'x-fsq-key',
        'Access-Control-Allow-Methods': 'GET, OPTIONS'
      },
      body: ''
    };
  }

  const apiKey = event.headers['x-fsq-key'];
  if (!apiKey) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Missing X-FSQ-Key header' }) };
  }

  const params = new URLSearchParams(event.queryStringParameters || {});
  const url = `https://places-api.foursquare.com/places/search?${params}`;

  try {
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'X-Places-Api-Version': '2025-06-17',
        Accept: 'application/json'
      }
    });

    const body = await response.text();
    return {
      statusCode: response.status,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body
    };
  } catch (err) {
    return {
      statusCode: 502,
      headers: { 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: err.message })
    };
  }
};
