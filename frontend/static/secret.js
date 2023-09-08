let secretEnvContext;

// create scope so that const values are scoped to this file
{

const {tr, td, input, textarea, button, span} = van.tags;

function getSecretsForRepository(provider, url) {
  const apiUrl = `/api/secret/repository?provider=${provider}&url=${encodeURIComponent(url)}`;

  cicadaFetch(apiUrl).then(resp => {
    if (resp.ok) {
      resp.json().then(keys => {
        for (const key of keys) {
          van.add(
            document.querySelector("table#secrets"),
            SecretRow(key),
          );

          onSecretListUpdate();
        }
      });
    } else {
      // TODO: handle
    }
  });
}

function getSecretsForInstallation(uuid) {
  cicadaFetch(`/api/secret/installation/${uuid}`).then(resp => {
    if (resp.ok) {
      resp.json().then(keys => {
        for (const key of keys) {
          van.add(
            document.querySelector("table#secrets"),
            SecretRow(key),
          );

          onSecretListUpdate();
        }
      });
    } else {
      // TODO: handle
    }
  });
}

function SecretRow(name) {
  const deleted = van.state(false);
  const saveable = van.state(false);
  const saved = van.state(false);
  const isSet = van.state(name !== undefined);
  const key = van.state(name || "");
  const value = van.state("");

  const deleteRow = () => {
    if (confirm("Are you sure you want to delete this secret?")) {
      const body = Object.assign({}, secretEnvContext, {key: key.val});

      cicadaFetch("/api/secret", {
        method: "DELETE",
        body: JSON.stringify(body),
        headers: {"Content-Type": "application/json"},
      }).then(resp => {
        if (resp.ok) {
          deleted.val = true;

          // Wait for Vanjs to update list
          setTimeout(onSecretListUpdate, 0);

        } else {
          // TODO: handle this
        }
      });
    }
  };

  const saveRow = () => {
    saved.val = true;
    saveable.val = false;
    isSet.val = true

    const body = Object.assign({}, secretEnvContext, {key: key.val, value: value.val});

    cicadaFetch(
      "/api/secret",
      {
        method: "PUT",
        body: JSON.stringify(body),
        headers: {"Content-Type": "application/json"},
      }
    );

    value.val = "";
  };

  const dirty = () => {
    saveable.val = true;
    saved.val = false;
  };

  let row = tr(
    td(
      input(
        {
          type: "text",
          name: "key",
          value: name ?? "",
          oninput: (e) => {
            key.val = e.target.value;
            dirty();
          },
          spellcheck: false,
          disabled: () => isSet.val,
        }
      )
    ),
    td(
      textarea(
        {
          type: "text",
          name: "value",
          value: value,
          oninput: (e) => {
            value.val = e.target.value;
            dirty();
          },
          autocomplete: "off",
          spellcheck: false,
        }
      )
    ),
    td(
      span(
        {class: "buttons"},
        button(
          {
            class: "save secret-save",
            onclick: saveRow,
            disabled: () => !saveable.val
          },
          () => isSet.val ? "Update" : "Save",
        ),
        button({class: "delete", onclick: deleteRow}, "Remove"),
        span(
          {
            class: "success-msg",
            style: () => saved.val ? "display: inline" : "display: none",
          },
          "Saved"
        ),
      ),
    )
  );

  return van.derive(() => deleted.val ? null : row);
}

function onClickSecret() {
  van.add(document.querySelector("table#secrets"), SecretRow());

  onSecretListUpdate();
}

function onSecretListUpdate() {
  // Subtract 1 for header
  const rowCount = document.querySelectorAll("table#secrets tr").length - 1;

  document.getElementById("no-secrets").style.display = rowCount ? "none" : "block";
}

// TODO: get actual URL from API
function getGitUrl(provider, shortUrl) {
  return `https://${provider}.com/${shortUrl}`;
}

}
