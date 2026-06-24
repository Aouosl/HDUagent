/**
 * 凌霄 安全模块 - API Key 加密存储 & Token 管理
 * HTTPS 环境使用 Web Crypto API，HTTP 环境降级为 Base64 编码
 */
window.Security = (function() {
    var STORAGE_PREFIX = "hdu_secure_";
    var hasCrypto = !!(window.crypto && window.crypto.subtle);

    function base64Encode(str) {
        try { return btoa(unescape(encodeURIComponent(str))); } catch(e) { return btoa(str); }
    }
    function base64Decode(str) {
        try { return decodeURIComponent(escape(atob(str))); } catch(e) { return atob(str); }
    }

    var ALGORITHM = { name: "AES-GCM", length: 256 };
    var _cryptoKey = null;

    async function getCryptoKey() {
        if (_cryptoKey) return _cryptoKey;
        var salt = sessionStorage.getItem("hdu_crypto_salt");
        if (!salt) {
            var bytes = crypto.getRandomValues(new Uint8Array(16));
            salt = Array.from(bytes).map(function(b) { return b.toString(16).padStart(2, "0"); }).join("");
            sessionStorage.setItem("hdu_crypto_salt", salt);
        }
        var enc = new TextEncoder();
        var base = [navigator.userAgent || "u", screen.width + "x" + screen.height, salt || "v1"].join("|");
        var km = await crypto.subtle.importKey("raw", enc.encode(base), "PBKDF2", false, ["deriveKey"]);
        _cryptoKey = await crypto.subtle.deriveKey(
            { name: "PBKDF2", salt: enc.encode("lingxiao-salt"), iterations: 100000, hash: "SHA-256" },
            km, ALGORITHM, false, ["encrypt", "decrypt"]
        );
        return _cryptoKey;
    }

    async function cryptoEncrypt(text) {
        if (!text) return "";
        var key = await getCryptoKey();
        var iv = crypto.getRandomValues(new Uint8Array(12));
        var enc = new TextEncoder().encode(text);
        var ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv: iv }, key, enc);
        var combined = new Uint8Array(iv.length + ct.byteLength);
        combined.set(iv);
        combined.set(new Uint8Array(ct), iv.length);
        return btoa(String.fromCharCode.apply(null, combined));
    }

    async function cryptoDecrypt(b64) {
        if (!b64) return "";
        try {
            var key = await getCryptoKey();
            var combined = Uint8Array.from(atob(b64), function(c) { return c.charCodeAt(0); });
            var iv = combined.slice(0, 12);
            var ct = combined.slice(12);
            var dec = await crypto.subtle.decrypt({ name: "AES-GCM", iv: iv }, key, ct);
            return new TextDecoder().decode(dec);
        } catch (e) {
            console.warn("解密失败，可能是新会话", e);
            return "";
        }
    }

    async function doEncrypt(text) {
        if (hasCrypto) return await cryptoEncrypt(text);
        return "b64:" + base64Encode(text);
    }

    async function doDecrypt(text) {
        if (!text) return "";
        if (text.indexOf("b64:") === 0) return base64Decode(text.slice(4));
        if (hasCrypto) return await cryptoDecrypt(text);
        return base64Decode(text);
    }

    return {
        secureSet: async function(key, value) {
            var encrypted = await doEncrypt(value);
            localStorage.setItem(STORAGE_PREFIX + key, encrypted);
        },
        secureGet: async function(key) {
            var encrypted = localStorage.getItem(STORAGE_PREFIX + key);
            if (!encrypted) return "";
            return await doDecrypt(encrypted);
        },
        secureRemove: function(key) {
            localStorage.removeItem(STORAGE_PREFIX + key);
        },

        plainSet: function(key, value) {
            localStorage.setItem("hdu_" + key, value);
        },
        plainGet: function(key) {
            return localStorage.getItem("hdu_" + key);
        },
        plainRemove: function(key) {
            localStorage.removeItem("hdu_" + key);
        },

        clearAll: function() {
            var toRemove = [];
            for (var i = localStorage.length - 1; i >= 0; i--) {
                var k = localStorage.key(i);
                if (k && (k.indexOf("hdu_") === 0 || k.indexOf(STORAGE_PREFIX) === 0)) {
                    toRemove.push(k);
                }
            }
            toRemove.forEach(function(k) { localStorage.removeItem(k); });
            sessionStorage.removeItem("hdu_crypto_salt");
        },

        hasCrypto: hasCrypto
    };
})();
