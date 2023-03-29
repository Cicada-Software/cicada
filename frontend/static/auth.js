const cicadaFetch = (url, args) => {
  const headers = new Headers(args?.["headers"]);

  args = args ?? {};
  args["headers"] = headers;

  const jwt = localStorage.getItem("jwt");
  if (jwt) headers.append("Authorization", "bearer " + jwt);

  return fetch(url, args);
};

const refreshToken = () => {
  cicadaFetch("/refresh_token", {method: "POST"})
    .then(resp => {
      if (resp.ok) {
        resp.json().then(j => {
          localStorage.setItem("jwt", j["access_token"]);
        });
      }
    })
    .catch(err => console.log({err}));
};

refreshToken();

setInterval(refreshToken, 60_000);

const logout = () => {
  if (confirm("Are you sure you want to log out?")) {
    localStorage.removeItem("jwt");
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
  cicadaFetch("/ping").then(e => {
    if (e.ok) return;

    const errorMsg = document.getElementById("error-msg");

    errorMsg.style.display = "block";
    errorMsg.innerText = httpStatusToMessage(e.status);
  });
};
