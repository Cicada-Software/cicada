window.addEventListener("DOMContentLoaded", () => {
  if (!areCookiesEnabled()) {
    displayCookieBanner();
  }
});

function enableCookies() {
  window.localStorage.setItem("allowFirstPartyCookies", true);
}

function areCookiesEnabled() {
  return !!window.localStorage.getItem("allowFirstPartyCookies");
}

function getKey(key) {
  return window.localStorage.getItem(key);
}

function setKey(key, value) {
  if (areCookiesEnabled()) {
    window.localStorage.setItem(key, value);
  }
}

function removeKey(key) {
  return window.localStorage.removeItem(key);
}

const cicadaFetch = (url, args) => {
  const headers = new Headers(args?.["headers"]);

  args = args ?? {};
  args["headers"] = headers;

  const jwt = getKey("jwt");
  if (jwt) headers.append("Authorization", "bearer " + jwt);

  return fetch(url, args);
};

const refreshToken = () => {
  cicadaFetch("/api/refresh_token", {method: "POST"})
    .then(resp => {
      if (resp.ok) {
        resp.json().then(j => {
          setKey("jwt", j["access_token"]);
        });
      } else if (resp.status === 401) {
        window.location = `/login?url=${encodeURI(window.location)}`;
      }
    })
    .catch(err => console.log({err}));
};

function refreshTokenLoop() {
  refreshToken();
  setInterval(refreshToken, 60_000);
}

const logout = (e) => {
  if (e.type === "keydown" && e.key !== "Enter") return;

  if (confirm("Are you sure you want to log out?")) {
    removeKey("jwt");
    window.location.href = "/login";
  }
};

const httpStatusToMessage = (code) => {
  switch (code) {
    case 401: return "Unauthorized, please try logging in";
    default: return "Something went wrong, please try again";
  }
};

const ping = () => {
  cicadaFetch("/api/ping").then(e => {
    if (e.ok) return;

    const errorMsg = document.getElementById("error-msg");

    errorMsg.style.display = "block";
    errorMsg.innerText = httpStatusToMessage(e.status);
  });
};

const getWebSocketUrl = () => {
  const socketUrl = new URL(window.location.href);

  // TODO: update this to wss only once I setup self-signed certs
  socketUrl.protocol = socketUrl.hostname == "localhost" ? "ws:" : "wss:";

  return socketUrl;
};

const normalizeProvider = (provider) => {
  switch (provider.toLowerCase()) {
    case "github": return "GitHub";
    case "gitlab": return "Gitlab";
    default: return provider;
  }
}

function displayCookieBanner() {
  const banner = document.createElement("div");

  banner.innerHTML = `
<div id="cookie-banner">
  <span class="message">
    Cicada only uses cookies that are strictly necessary for providing our services.
    We do not use cookies for advertising purposes.
    You can read our <a href="/cookies">Cookie Policy here</a>.
  </span>

  <button id="accept-cookies">Accept</button>
</div>

<style>
#cookie-banner-wrapper {
  z-index: 1;
  position: fixed;
  bottom: 0;
  left: 0;

  width: 100%;
}

#cookie-banner {
  display: flex;
  gap: 1em;
  background: #eee;
  margin: 0 auto 2em auto;
  padding: 1em;
  border-radius: 0.5em;
  max-width: calc(100% - 4em);
  width: fit-content;
  box-shadow: rgba(0, 0, 0, 0.25) 0px 14px 28px, rgba(0, 0, 0, 0.22) 0px 10px 10px;
}

#cookie-banner .message {
  flex: 1;
  margin: auto;
}

#accept-cookies {
  margin: auto;
  height: min-content;
  color: #eee;
  background: #3b3bff;
  border-radius: 0.3em;
}
</style>`;

  banner.id = "cookie-banner-wrapper";
  banner.querySelector("#accept-cookies").onclick = () => {
    enableCookies();
    disableCookieBanner();

    window.location.reload();
  };

  document.body.insertAdjacentElement("beforebegin", banner);
}

function disableCookieBanner() {
  document.getElementById("cookie-banner-wrapper").style.display = "none";
}

class Navbar extends HTMLElement {
  constructor() {
    super();
  }

  connectedCallback() {
    const template = document.createElement("template");

    const version = "Cicada v1.0.0";

    template.innerHTML = `
<div id="navbar">
  <a href="/dashboard" id="back" part="back">&#8592; Back</a>
  <slot></slot>
  <span id="version" part="version">${version}</span>
  <img
    id="logout"
    src="/static/img/logout.svg"
    onclick="logout(event)"
    onkeydown="logout(event)"
    tabindex=0
  />
</div>

<style>
#navbar {
  display: flex;
  flex-direction: row;
  gap: 1em;
  margin: 0;
  color: var(--white);
  font-weight: bold;
}

#navbar > *, ::slotted(*) {
  padding: 0.5em;
  background: var(--gray);
  border-radius: var(--border-radius);
}

.navbar-filler {
  flex: 1;
  text-align: right;
}

#back {
  transition: background 150ms;
}

#back:hover {
  background: var(--medium-gray);
}

#version {
  color: var(--lightgray);
  flex: 1;
  text-align: right;
  cursor: default;
}

#logout {
  cursor: pointer;
  padding: 0.4em !important;
  height: min-content;
  transition: background 150ms;
}

#logout:hover {
  background: var(--medium-gray);
}

a {
  color: var(--blue);
}
</style>
    `;

    const shadow = this.attachShadow({ mode: "open" });
    shadow.appendChild(template.content.cloneNode(true));
  }
}

customElements.define("top-navbar", Navbar)
