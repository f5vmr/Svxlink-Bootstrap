"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const page = document.querySelector("[data-status-url]");
  const form = document.getElementById("installation-form");
  const button = document.getElementById("install-button");
  const requestError = document.getElementById("request-error");
  const inspectionPanel = document.getElementById(
    "inspection-panel"
  );
  const progressPanel = document.getElementById(
    "progress-panel"
  );
  const completionPanel = document.getElementById(
    "completion-panel"
  );
  const progressMessage = document.getElementById(
    "progress-message"
  );
  const installationLog = document.getElementById(
    "installation-log"
  );

  if (!page) {
    return;
  }

  const statusUrl = page.dataset.statusUrl;
  let pollTimer = null;

  function stageClass(status) {
    if (status === "completed") {
      return "complete";
    }

    return status;
  }

  function renderStages(stages) {
    document.querySelectorAll("[data-stage]").forEach(
      (element) => {
        const stage = element.dataset.stage;
        const status = stages[stage] || "pending";

        element.classList.remove(
          "running",
          "complete",
          "failed",
          "skipped"
        );

        if (status !== "pending") {
          element.classList.add(stageClass(status));
        }
      }
    );
  }

  function renderState(state) {
    renderStages(state.stages);

    progressMessage.textContent = (
      state.message || "Installation is running."
    );

    installationLog.textContent = state.log.join("\n");
    installationLog.scrollTop = (
      installationLog.scrollHeight
    );

    if (state.status === "completed") {
      window.clearTimeout(pollTimer);
      progressPanel.classList.add("hidden");
      completionPanel.classList.remove("hidden");

      if (state.redirect_url) {
        window.setTimeout(() => {
          window.location.assign(state.redirect_url);
        }, 1500);
      }

      return false;
    }

    if (state.status === "failed") {
      window.clearTimeout(pollTimer);
      return false;
    }

    return true;
  }

  async function pollStatus() {
    try {
      const response = await fetch(statusUrl, {
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(
          `Status request failed (${response.status}).`
        );
      }

      const state = await response.json();
      const continuePolling = renderState(state);

      if (continuePolling) {
        pollTimer = window.setTimeout(
          pollStatus,
          750
        );
      }
    } catch (error) {
      progressMessage.textContent = error.message;
      pollTimer = window.setTimeout(
        pollStatus,
        1500
      );
    }
  }

  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    requestError.classList.add("hidden");
    requestError.textContent = "";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        const message = await response.text();

        throw new Error(
          message || (
            `Installation request failed `
            + `(${response.status}).`
          )
        );
      }

      inspectionPanel.classList.add("hidden");
      progressPanel.classList.remove("hidden");
      pollStatus();
    } catch (error) {
      requestError.textContent = error.message;
      requestError.classList.remove("hidden");
      button.disabled = false;
    }
  });
});
