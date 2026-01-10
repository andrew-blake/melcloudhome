// Chrome Console Snippet: Block and Log API Mutations
// Intercepts POST/PUT/PATCH/DELETE requests to MELCloud API and logs payloads
// Returns 200 success so the UI thinks the command worked
//
// Usage:
//   blockMutations()    - Enable blocking (blocks POST/PUT/PATCH/DELETE)
//   unblockMutations()  - Disable blocking (restore normal behavior)

(function() {
  // State tracking
  let isBlocking = false;
  let originalFetch = null;

  // Blocking implementation
  function createBlockingFetch(original) {
    return function(...args) {
      const [url, options = {}] = args;
      const method = (options.method || 'GET').toUpperCase();

      // Check if it's a mutation request to API endpoints
      const mutationMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
      if (mutationMethods.includes(method) && url.includes('/api/')) {
        console.group(`🔄 PROXIED ${method} Request`);
        console.log('Original URL:', url);

        // Build mock server URL
        const mockUrl = url
          .replace('https://melcloudhome.com', 'http://localhost:8080')
          .replace('https://api.melcloud.com', 'http://localhost:8080');

        console.log('Mock Server URL:', mockUrl);
        console.log('Method:', method);

        // Log request headers
        if (options.headers) {
          console.log('Request Headers:', options.headers);
        }

        // Log request body (parse if JSON)
        let bodyData = null;
        if (options.body) {
          try {
            bodyData = JSON.parse(options.body);
            console.log('Request Body (JSON):');
            console.log(JSON.stringify(bodyData, null, 2));
          } catch (e) {
            console.log('Request Body (raw):', options.body);
          }
        }

        // Send to mock server (async, don't wait)
        original(mockUrl, {
          ...options,
          mode: 'cors',
        })
          .then(async (mockResponse) => {
            console.log('Mock Server Status:', mockResponse.status);
            try {
              const mockBody = await mockResponse.text();
              if (mockBody) {
                console.log('Mock Server Response:', mockBody);
              } else {
                console.log('Mock Server Response: (empty)');
              }
            } catch (e) {
              console.log('Mock Server Response: (error reading)');
            }
          })
          .catch((err) => {
            console.error('❌ Mock Server Error:', err.message);
          })
          .finally(() => {
            console.groupEnd();
          });

        // Immediately return fake 200 to web client (don't wait for mock server)
        return Promise.resolve(new Response(
          JSON.stringify({ success: true }),
          {
            status: 200,
            statusText: 'OK',
            headers: {
              'Content-Type': 'application/json'
            }
          }
        ));
      }

      // Let other requests through normally
      return original.apply(this, args);
    };
  }

  // Register blocking
  window.blockMutations = function() {
    if (isBlocking) {
      console.log('⚠️  Mutation blocking already enabled');
      return;
    }

    // Store original fetch if not already stored
    if (!originalFetch) {
      originalFetch = window.fetch;
    }

    // Install blocking fetch
    window.fetch = createBlockingFetch(originalFetch);
    isBlocking = true;

    console.log('✅ Request blocking ENABLED');
    console.log('📝 All POST/PUT/PATCH/DELETE requests will be logged');
    console.log('🔄 UI will receive fake 200 success responses');
    console.log('💡 To disable: unblockMutations()');
  };

  // Unregister blocking
  window.unblockMutations = function() {
    if (!isBlocking) {
      console.log('⚠️  Mutation blocking already disabled');
      return;
    }

    // Restore original fetch
    if (originalFetch) {
      window.fetch = originalFetch;
    }
    isBlocking = false;

    console.log('✅ Mutation blocking DISABLED');
    console.log('🔄 API calls will now go through normally');
    console.log('💡 To re-enable: blockMutations()');
  };

  // Unload script completely
  window.unloadMutationScript = function() {
    // Restore original fetch if blocking is active
    if (isBlocking && originalFetch) {
      window.fetch = originalFetch;
    }

    // Clean up all functions and state
    delete window.blockMutations;
    delete window.unblockMutations;
    delete window.unloadMutationScript;
    delete window._mutationBlockingRegistered;

    console.log('🗑️  Mutation blocking script UNLOADED');
    console.log('💡 Re-run snippet to reload');
  };

  // Check if already registered
  if (window._mutationBlockingRegistered) {
    console.log('⚠️  Script already loaded. Use blockMutations() / unblockMutations()');
    return;
  }

  // Mark as registered
  window._mutationBlockingRegistered = true;

  console.log('📦 API mutation blocking script loaded');
  console.log('');
  console.log('Commands:');
  console.log('  blockMutations()       - Enable blocking (POST/PUT/PATCH/DELETE)');
  console.log('  unblockMutations()     - Disable blocking');
  console.log('  unloadMutationScript() - Unload script completely');
  console.log('');
  console.log('💡 Run blockMutations() to start');
})();
