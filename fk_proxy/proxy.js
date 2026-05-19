// src/index.js
var index_default = {
  async fetch(request) {
    if (request.method !== "POST" || new URL(request.url).pathname !== "/flipkart_check") {
      return new Response("Not Found or Method Not Allowed", { status: 404 });
    }
    try {
      const data = await request.json();
      const productId = data.productId;
      const pincode = data.pincode || "132001";
      if (!productId) {
        return new Response(JSON.stringify({ error: "Missing 'productId' in request body" }), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        });
      }
      const flipkartRequestBody = {
        requestContext: {
          products: [{ productId }],
          marketplace: "FLIPKART"
        },
        locationContext: { pincode }
      };
      const flipkartResponse = await fetch("https://2.rome.api.flipkart.com/api/3/product/serviceability", {
        method: "POST",
        headers: {
          // Replicating the required headers
          "Accept": "application/json",
          "Content-Type": "application/json",
          "Origin": "https://www.flipkart.com",
          "Referer": "https://www.flipkart.com",
          // --- CHANGED: Using a common Desktop User-Agent ---
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36",
          // Keeping the X-User-Agent for Flipkart's internal check
          "X-User-Agent": "Mozilla/5.0 FKUA/msite/0.0.3/msite/Mobile",
          "flipkart_secure": "true"
        },
        body: JSON.stringify(flipkartRequestBody)
      });
      if (!flipkartResponse.ok) {
        const errorText = await flipkartResponse.text();
        return new Response(JSON.stringify({
          error: `Flipkart API failed with status ${flipkartResponse.status}`,
          details: errorText.substring(0, 200)
          // Limit size of error detail
        }), {
          status: 502,
          // Bad Gateway or Service Unavailable
          headers: { "Content-Type": "application/json" }
        });
      }
      const flipkartData = await flipkartResponse.json();
      return new Response(JSON.stringify(flipkartData), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: `Internal Server Error: ${e.message}` }), {
        status: 500,
        headers: { "Content-Type": "application/json" }
      });
    }
  }
};
export {
  index_default as default
};
//# sourceMappingURL=index.js.map
