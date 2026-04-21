function getCsrfToken() {
  const el = document.querySelector('meta[name="csrf-token"]');
  return el ? el.getAttribute("content") : "";
}

// Wrapper around fetch that automatically includes CSRF token and JSON content type
async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  const csrf = getCsrfToken();
  if (csrf) {
    headers["X-CSRFToken"] = csrf;
    headers["X-CSRF-Token"] = csrf;
  }
  headers["Content-Type"] = headers["Content-Type"] || "application/json";
  const res = await fetch(url, { ...options, headers });
  return res;
}

const INGREDIENT_UNIT_OPTIONS = ["", "g", "kg", "ml", "l", "tsp", "tbsp", "cup", "cups", "piece", "pieces", "slice", "slices", "pinch", "to taste"];

// Utility functions to check if a file is a supported image or video type

function isSupportedImageFile(file) {
  if (!file) return false;
  const name = String(file.name || "").toLowerCase();
  const mime = String(file.type || "").toLowerCase();
  return mime.startsWith("image/") || [".png", ".jpg", ".jpeg", ".webp"].some((ext) => name.endsWith(ext));
}

function isSupportedVideoFile(file) {
  if (!file) return false;
  const name = String(file.name || "").toLowerCase();
  const mime = String(file.type || "").toLowerCase();
  return (
    mime.startsWith("video/") ||
    [".mp4", ".webm", ".ogv"].some((ext) => name.endsWith(ext))
  );
}

// Function to set up a dynamic list of items (like ingredients), with add/remove functionality and synchronization to a hidden textarea for form submission
function setupDynamicList({ containerId, addBtnId, hiddenTextareaId, initialItems, placeholder, clientErrorId }) {
  const container = document.getElementById(containerId);
  const addBtn = document.getElementById(addBtnId);
  const hidden = document.getElementById(hiddenTextareaId);
  if (!container || !addBtn || !hidden) return;

  const clientErrorEl = clientErrorId ? document.getElementById(clientErrorId) : null;
  const showIngredientsClientError = (message) => {
    if (clientErrorEl) {
      clientErrorEl.textContent = message;
      clientErrorEl.hidden = false;
    } else {
      window.alert(message);
    }
  };
  const clearIngredientsClientError = () => {
    if (clientErrorEl) {
      clientErrorEl.textContent = "";
      clientErrorEl.hidden = true;
    }
  };

  const items = [...(initialItems || [])];

  const sync = () => {
    hidden.value = items.join("\n");
    if (hidden.value.trim()) clearIngredientsClientError();
  };

  const render = () => {
    container.innerHTML = "";
    items.forEach((value, idx) => {
      const row = document.createElement("div");
      row.className = "dyn-row";

      const input = document.createElement("input");
      input.className = "input";
      input.placeholder = placeholder;
      input.value = value;
      input.addEventListener("input", (e) => {
        items[idx] = e.target.value.trim();
        sync();
      });

      const del = document.createElement("button");
      del.type = "button";
      del.className = "icon-btn";
      del.textContent = "✕";
      del.title = "Remove";
      del.addEventListener("click", () => {
        items.splice(idx, 1);
        sync();
        render();
      });

      row.appendChild(input);
      row.appendChild(del);
      container.appendChild(row);
    });

    if (items.length === 0) {
      const empty = document.createElement("div");
      empty.className = "muted small";
      empty.textContent = "No items yet.";
      container.appendChild(empty);
    }
  };

  addBtn.addEventListener("click", () => {
    items.push("");
    sync();
    render();
    const lastInput = container.querySelector(".dyn-row:last-child input");
    if (lastInput) lastInput.focus();
  });

  const form = container.closest("form");
  if (form) {
    form.addEventListener("submit", (event) => {
      sync();
      if (!hidden.value.trim()) {
        event.preventDefault();
        showIngredientsClientError(
          "Please add at least one ingredient. Use “+ Add ingredient”, then enter a name (and optionally amount and unit)."
        );
        addBtn.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }

  sync();
  render();
}

// Ingredient editor that parses input into name, amount, and unit, with support for client-side validation and error display
function setupIngredientEditor({ containerId, addBtnId, hiddenTextareaId, initialItems, clientErrorId }) {
  const container = document.getElementById(containerId);
  const addBtn = document.getElementById(addBtnId);
  const hidden = document.getElementById(hiddenTextareaId);
  if (!container || !addBtn || !hidden) return;

  const clientErrorEl = clientErrorId ? document.getElementById(clientErrorId) : null;
  const showIngredientsClientError = (message) => {
    if (clientErrorEl) {
      clientErrorEl.textContent = message;
      clientErrorEl.hidden = false;
    } else {
      window.alert(message);
    }
  };
  const clearIngredientsClientError = () => {
    if (clientErrorEl) {
      clientErrorEl.textContent = "";
      clientErrorEl.hidden = true;
    }
  };
  const parseIngredient = (value) => {
    const text = String(value || "").trim();
    if (!text) return { name: "", amount: "", unit: "" };

    const separatorMatch = text.match(/^(.*?)\s+[-:|]\s+(.*)$/);
    if (separatorMatch) {
      const left = separatorMatch[1].trim();
      const parts = left.split(/\s+/);
      const maybeUnit = parts.length > 1 ? parts[parts.length - 1] : "";
      return {
        amount: parts[0] || "",
        unit: INGREDIENT_UNIT_OPTIONS.includes(maybeUnit) ? maybeUnit : "",
        name: separatorMatch[2].trim(),
      };
    }

    const compactMatch = text.match(/^(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)?\s+(.+)$/);
    if (compactMatch) {
      const parsedUnit = compactMatch[2] || "";
      return {
        amount: compactMatch[1] || "",
        unit: INGREDIENT_UNIT_OPTIONS.includes(parsedUnit) ? parsedUnit : "",
        name: compactMatch[3].trim(),
      };
    }

    return { name: text, amount: "", unit: "" };
  };

  const items = (initialItems || []).map((value) => parseIngredient(value));

  const sync = () => {
    hidden.value = items
      .map((item) => {
        const name = item.name.trim();
        const amount = String(item.amount || "").trim();
        const unit = item.unit.trim();
        const quantity = [amount, unit].filter(Boolean).join(" ").trim();
        if (!name && !quantity) return "";
        if (!quantity) return name;
        if (!name) return quantity;
        return `${quantity} ${name}`;
      })
      .filter(Boolean)
      .join("\n");
    if (hidden.value.trim()) clearIngredientsClientError();
  };

  const render = () => {
    container.innerHTML = "";
    items.forEach((item, idx) => {
      const row = document.createElement("div");
      row.className = "ingredient-row";

      const nameInput = document.createElement("input");
      nameInput.className = "input";
      nameInput.placeholder = "Ingredient";
      nameInput.value = item.name;
      nameInput.addEventListener("input", (event) => {
        items[idx].name = event.target.value;
        sync();
      });

      const quantityInput = document.createElement("input");
      quantityInput.className = "input";
      quantityInput.placeholder = "Amount";
      quantityInput.value = item.amount;
      quantityInput.addEventListener("input", (event) => {
        items[idx].amount = event.target.value;
        sync();
      });

      const unitSelect = document.createElement("select");
      unitSelect.className = "input";
      unitSelect.innerHTML = INGREDIENT_UNIT_OPTIONS
        .map((unit) => `<option value="${unit}">${unit || "Unit"}</option>`)
        .join("");
      unitSelect.value = item.unit;
      unitSelect.addEventListener("change", (event) => {
        items[idx].unit = event.target.value;
        sync();
      });

      const del = document.createElement("button");
      del.type = "button";
      del.className = "icon-btn";
      del.textContent = "✕";
      del.title = "Remove";
      del.addEventListener("click", () => {
        items.splice(idx, 1);
        sync();
        render();
      });

      row.appendChild(nameInput);
      row.appendChild(quantityInput);
      row.appendChild(unitSelect);
      row.appendChild(del);
      container.appendChild(row);
    });

    if (items.length === 0) {
      const empty = document.createElement("div");
      empty.className = "muted small";
      empty.textContent = "No ingredients yet.";
      container.appendChild(empty);
    }
  };

  addBtn.addEventListener("click", () => {
    items.push({ name: "", amount: "", unit: "" });
    sync();
    render();
    const lastInput = container.querySelector(".ingredient-row:last-child input");
    if (lastInput) lastInput.focus();
  });

  const form = container.closest("form");
  if (form) {
    form.addEventListener("submit", (event) => {
      sync();
      if (!hidden.value.trim()) {
        event.preventDefault();
        showIngredientsClientError(
          "Please add at least one ingredient. Use “+ Add ingredient”, then enter a name (and optionally amount and unit)."
        );
        addBtn.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }

  sync();
  render();
}

// Step editor that supports text, image, and video steps
function setupStepEditor({ containerId, addContentBtnId, addImageBtnId, addVideoBtnId, hiddenInputId, legacyTextareaId, initialSteps }) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const stepToolbar =
    container.previousElementSibling &&
    container.previousElementSibling.classList &&
    container.previousElementSibling.classList.contains("step-editor-toolbar")
      ? container.previousElementSibling
      : null;

  const form = container.closest("form");
  let hiddenInput = document.getElementById(hiddenInputId);
  let legacyTextarea = document.getElementById(legacyTextareaId);

  if (!hiddenInput && form) {
    hiddenInput = document.createElement("textarea");
    hiddenInput.id = hiddenInputId;
    hiddenInput.name = "steps_data";
    hiddenInput.className = "input hidden";
    form.appendChild(hiddenInput);
  }

  if (!legacyTextarea && form) {
    legacyTextarea = document.createElement("textarea");
    legacyTextarea.id = legacyTextareaId;
    legacyTextarea.name = "steps_text";
    legacyTextarea.className = "input hidden";
    form.appendChild(legacyTextarea);
  }

  if (!hiddenInput || !legacyTextarea) return;

  const createStepState = (step = {}) => {
    const type =
      step.type === "image" ? "image" : step.type === "video" ? "video" : "content";
    const previewUrl =
      type === "image"
        ? step.image_url || ""
        : type === "video"
          ? step.video_url || ""
          : "";
    return {
      clientId: `step_${Math.random().toString(36).slice(2, 10)}`,
      type,
      title: step.title || "",
      description_markdown: step.description_markdown || "",
      ingredients: Array.isArray(step.ingredients)
        ? step.ingredients.map((ingredient) => ({
            name: ingredient.name || "",
            amount: ingredient.amount ?? ingredient.grams ?? "",
            unit: ingredient.unit || (ingredient.grams != null ? "g" : ""),
          }))
        : [],
      image_storage_key: step.image_storage_key || "",
      image_url: step.image_url || "",
      video_storage_key: step.video_storage_key || "",
      video_url: step.video_url || "",
      previewUrl,
      uploadField: "",
      file: null,
      fileInput: null,
    };
  };

  const steps = Array.isArray(initialSteps) && initialSteps.length
    ? initialSteps.map((step) => createStepState(step))
    : [createStepState()];

  const ensureAtLeastOneStep = () => {
    if (!steps.length) steps.push(createStepState());
  };

  const sync = () => {
    const payload = steps.map((step) => {
      if (step.type === "image") {
        const imageStep = {
          type: "image",
          image_storage_key: step.image_storage_key || "",
          image_url: step.image_url || "",
        };
        if (step.file) imageStep.upload_field = step.uploadField;
        return imageStep;
      }
      if (step.type === "video") {
        const videoStep = {
          type: "video",
          video_storage_key: step.video_storage_key || "",
          video_url: step.video_url || "",
        };
        if (step.file) videoStep.upload_field = step.uploadField;
        return videoStep;
      }
      return {
        type: "content",
        title: step.title.trim(),
        description_markdown: step.description_markdown.trim(),
        ingredients: step.ingredients
          .filter((ingredient) => ingredient.name.trim() || String(ingredient.amount).trim() || ingredient.unit.trim())
          .map((ingredient) => ({
            name: ingredient.name.trim(),
            amount: String(ingredient.amount).trim(),
            unit: ingredient.unit.trim(),
          })),
      };
    });

    hiddenInput.value = JSON.stringify(payload);
    legacyTextarea.value = payload
      .map((step, index) => {
        if (step.type === "image") return `${index + 1}. [Image]`;
        if (step.type === "video") return `${index + 1}. [Video]`;
        if (step.title && step.description_markdown) return `${index + 1}. ${step.title}: ${step.description_markdown}`;
        return `${index + 1}. ${step.description_markdown || step.title}`;
      })
      .join("\n");
  };

  const safeRender = () => {
    try {
      render();
    } catch (error) {
      container.innerHTML = "";
      const failure = document.createElement("div");
      failure.className = "flash danger";
      failure.textContent = "Step editor could not be initialized. Please reload the page.";
      container.appendChild(failure);
    }
  };

  const renderStepControls = (index) => {
    const controls = document.createElement("div");
    controls.className = "step-card-controls";

    const moveUpBtn = document.createElement("button");
    moveUpBtn.type = "button";
    moveUpBtn.className = "icon-btn";
    moveUpBtn.textContent = "Up";
    moveUpBtn.disabled = index === 0;
    moveUpBtn.addEventListener("click", () => {
      if (index === 0) return;
      [steps[index - 1], steps[index]] = [steps[index], steps[index - 1]];
      safeRender();
    });

    const moveDownBtn = document.createElement("button");
    moveDownBtn.type = "button";
    moveDownBtn.className = "icon-btn";
    moveDownBtn.textContent = "Down";
    moveDownBtn.disabled = index === steps.length - 1;
    moveDownBtn.addEventListener("click", () => {
      if (index === steps.length - 1) return;
      [steps[index], steps[index + 1]] = [steps[index + 1], steps[index]];
      safeRender();
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "icon-btn";
    removeBtn.textContent = "✕";
    removeBtn.title = "Remove step";
    removeBtn.addEventListener("click", () => {
      steps.splice(index, 1);
      ensureAtLeastOneStep();
      safeRender();
    });

    controls.appendChild(moveUpBtn);
    controls.appendChild(moveDownBtn);
    controls.appendChild(removeBtn);
    return controls;
  };

  const renderInsertControls = (insertIndex) => {
    const insertWrap = document.createElement("div");
    insertWrap.className = "step-insert-zone";
    insertWrap.setAttribute("aria-label", `Insert step at position ${insertIndex + 1}`);

    const insertActions = document.createElement("div");
    insertActions.className = "step-insert-actions";

    const buildInsertBtn = (label, type) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn secondary";
      button.textContent = label;
      button.addEventListener("click", () => {
        insertStepType(type, insertIndex);
      });
      return button;
    };

    insertActions.appendChild(buildInsertBtn("+ Add text step", "content"));
    insertActions.appendChild(buildInsertBtn("+ Add image step", "image"));
    insertActions.appendChild(buildInsertBtn("+ Add video step", "video"));
    insertWrap.appendChild(insertActions);
    return insertWrap;
  };

  const renderIngredientRow = (step, ingredient, ingredientIndex) => {
    const row = document.createElement("div");
    row.className = "step-ingredient-row";

    const nameInput = document.createElement("input");
    nameInput.className = "input";
    nameInput.placeholder = "Ingredient";
    nameInput.value = ingredient.name;
    nameInput.addEventListener("input", (event) => {
      step.ingredients[ingredientIndex].name = event.target.value;
      sync();
    });

      const gramsInput = document.createElement("input");
      gramsInput.className = "input";
      gramsInput.type = "text";
      gramsInput.placeholder = "Amount";
      gramsInput.value = ingredient.amount;
      gramsInput.addEventListener("input", (event) => {
        step.ingredients[ingredientIndex].amount = event.target.value;
        sync();
      });

      const unitSelect = document.createElement("select");
      unitSelect.className = "input";
      unitSelect.innerHTML = INGREDIENT_UNIT_OPTIONS
        .map((unit) => `<option value="${unit}">${unit || "Unit"}</option>`)
        .join("");
      unitSelect.value = ingredient.unit;
      unitSelect.addEventListener("change", (event) => {
        step.ingredients[ingredientIndex].unit = event.target.value;
        sync();
      });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "icon-btn";
    removeBtn.textContent = "✕";
    removeBtn.title = "Remove ingredient";
    removeBtn.addEventListener("click", () => {
      step.ingredients.splice(ingredientIndex, 1);
      safeRender();
    });

      row.appendChild(nameInput);
      row.appendChild(gramsInput);
      row.appendChild(unitSelect);
      row.appendChild(removeBtn);
      return row;
  };

  const render = () => {
    container.innerHTML = "";
    ensureAtLeastOneStep();

    steps.forEach((step, index) => {
      const card = document.createElement("section");
      card.className = "step-card";

      const head = document.createElement("div");
      head.className = "step-card-head";
      const heading = document.createElement("strong");
      heading.textContent = `Step ${index + 1}`;
      head.appendChild(heading);
      head.appendChild(renderStepControls(index));
      card.appendChild(head);

      const typeField = document.createElement("div");
      typeField.className = "field";
      const typeLabel = document.createElement("label");
      typeLabel.textContent = "Step type";
      typeField.appendChild(typeLabel);
      const typeSelect = document.createElement("select");
      typeSelect.className = "input";
      typeSelect.innerHTML =
        '<option value="content">Text</option><option value="image">Image</option><option value="video">Video</option>';
      typeSelect.value = step.type;
      typeSelect.addEventListener("change", (event) => {
        const nextType = event.target.value;
        if (nextType === step.type) return;
        if (nextType === "content") {
          Object.assign(step, createStepState({ type: "content" }), { clientId: step.clientId });
        } else if (nextType === "image") {
          Object.assign(step, createStepState({ type: "image" }), { clientId: step.clientId });
        } else {
          Object.assign(step, createStepState({ type: "video" }), { clientId: step.clientId });
        }
        safeRender();
      });
      typeField.appendChild(typeSelect);
      card.appendChild(typeField);

      if (step.type === "content") {
        const titleField = document.createElement("div");
        titleField.className = "field";
        titleField.innerHTML = "<label>Title</label>";
        const titleInput = document.createElement("input");
        titleInput.className = "input";
        titleInput.placeholder = "e.g., Toast the spices";
        titleInput.value = step.title;
        titleInput.addEventListener("input", (event) => {
          step.title = event.target.value;
          sync();
        });
        titleField.appendChild(titleInput);
        card.appendChild(titleField);

        const descriptionField = document.createElement("div");
        descriptionField.className = "field";
        descriptionField.innerHTML = "<label>Description (Markdown)</label>";
        const descriptionInput = document.createElement("textarea");
        descriptionInput.className = "input";
        descriptionInput.rows = 6;
        descriptionInput.placeholder = "Describe this step in markdown...";
        descriptionInput.value = step.description_markdown;
        descriptionInput.addEventListener("input", (event) => {
          step.description_markdown = event.target.value;
          sync();
        });
        descriptionField.appendChild(descriptionInput);
        card.appendChild(descriptionField);

        const ingredientsField = document.createElement("div");
        ingredientsField.className = "field";
        ingredientsField.innerHTML = '<label>Ingredients for this step</label><div class="muted small">Optional. Name, amount, and unit for ingredients that apply only to this step.</div>';
        const ingredientsList = document.createElement("div");
        ingredientsList.className = "step-ingredients-list";
        if (step.ingredients.length) {
          step.ingredients.forEach((ingredient, ingredientIndex) => {
            ingredientsList.appendChild(renderIngredientRow(step, ingredient, ingredientIndex));
          });
        } else {
          const emptyState = document.createElement("div");
          emptyState.className = "muted small";
          emptyState.textContent = "No step ingredients yet.";
          ingredientsList.appendChild(emptyState);
        }
        ingredientsField.appendChild(ingredientsList);

        const addIngredientBtn = document.createElement("button");
        addIngredientBtn.type = "button";
        addIngredientBtn.className = "btn secondary add-step-ingredient-btn";
        addIngredientBtn.textContent = "+ Add step ingredient";
        addIngredientBtn.addEventListener("click", () => {
          step.ingredients.push({ name: "", amount: "", unit: "" });
          safeRender();
        });
        ingredientsField.appendChild(addIngredientBtn);
        card.appendChild(ingredientsField);
      } else if (step.type === "image") {
        step.uploadField = `step_image_${step.clientId}`;
        const imageField = document.createElement("div");
        imageField.className = "field";
        imageField.innerHTML = '<label>Step image</label><div class="muted small">Upload a new image or keep the existing step image.</div>';

        if (!step.fileInput) {
          const fileInput = document.createElement("input");
          fileInput.className = "input";
          fileInput.type = "file";
          fileInput.accept = ".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp";
          fileInput.addEventListener("change", (event) => {
            const [file] = event.target.files || [];
            if (file && !isSupportedImageFile(file)) {
              event.target.value = "";
              step.file = null;
              step.previewUrl = step.image_url || "";
              alert("Please choose a png, jpg, jpeg, or webp image.");
              sync();
              safeRender();
              return;
            }
            step.file = file || null;
            step.previewUrl = file ? URL.createObjectURL(file) : (step.image_url || "");
            sync();
            safeRender();
          });
          step.fileInput = fileInput;
        }
        step.fileInput.name = step.uploadField;
        imageField.appendChild(step.fileInput);

        if (step.previewUrl) {
          const preview = document.createElement("img");
          preview.className = "step-editor-preview";
          preview.src = step.previewUrl;
          preview.alt = `Preview for step ${index + 1}`;
          imageField.appendChild(preview);
        }

        card.appendChild(imageField);
      } else {
        step.uploadField = `step_video_${step.clientId}`;
        const videoField = document.createElement("div");
        videoField.className = "field";
        videoField.innerHTML =
          '<label>Step video</label><div class="muted small">Upload mp4, webm, or ogv, or keep the existing step video.</div>';

        if (!step.fileInput) {
          const fileInput = document.createElement("input");
          fileInput.className = "input";
          fileInput.type = "file";
          fileInput.accept = ".mp4,.webm,.ogv,video/mp4,video/webm,video/ogg";
          fileInput.addEventListener("change", (event) => {
            const [file] = event.target.files || [];
            if (file && !isSupportedVideoFile(file)) {
              event.target.value = "";
              step.file = null;
              step.previewUrl = step.video_url || "";
              alert("Please choose an mp4, webm, or ogv video.");
              sync();
              safeRender();
              return;
            }
            step.file = file || null;
            step.previewUrl = file ? URL.createObjectURL(file) : (step.video_url || "");
            sync();
            safeRender();
          });
          step.fileInput = fileInput;
        }
        step.fileInput.name = step.uploadField;
        videoField.appendChild(step.fileInput);

        if (step.previewUrl) {
          const preview = document.createElement("video");
          preview.className = "step-editor-preview";
          preview.controls = true;
          preview.src = step.previewUrl;
          preview.setAttribute("playsinline", "");
          videoField.appendChild(preview);
        }

        card.appendChild(videoField);
      }

      container.appendChild(card);
      if (index < steps.length - 1) {
        container.appendChild(renderInsertControls(index + 1));
      }
    });

    sync();
  };

  const insertStepType = (type, index = steps.length) => {
    const boundedIndex = Math.max(0, Math.min(index, steps.length));
    steps.splice(boundedIndex, 0, createStepState({ type }));
    safeRender();
  };

  if (stepToolbar) {
    stepToolbar.addEventListener("click", (event) => {
      const btn = event.target && event.target.closest ? event.target.closest("button") : null;
      if (!btn || btn.disabled || btn.type === "submit") return;
      const id = btn.id;
      if (id === addContentBtnId) {
        event.preventDefault();
        insertStepType("content");
      } else if (id === addImageBtnId) {
        event.preventDefault();
        insertStepType("image");
      } else if (id === addVideoBtnId) {
        event.preventDefault();
        insertStepType("video");
      }
    });
  } else {
    const addContentBtn = document.getElementById(addContentBtnId);
    const addImageBtn = document.getElementById(addImageBtnId);
    const addVideoBtn = document.getElementById(addVideoBtnId);
    if (addContentBtn) addContentBtn.addEventListener("click", () => insertStepType("content"));
    if (addImageBtn) addImageBtn.addEventListener("click", () => insertStepType("image"));
    if (addVideoBtn) addVideoBtn.addEventListener("click", () => insertStepType("video"));
  }

  safeRender();
}

// Utility function to format an ingredient line for display
function formatComputedIngredientLine(item) {
  let t = "";
  if (item.displayAmount) t += String(item.displayAmount);
  if (item.displayUnit) t += (t ? " " : "") + String(item.displayUnit);
  if (t) t += " ";
  t += item.name || "";
  if (item.note) t += ` (${item.note})`;
  return t.trim() || item.name || "";
}

// Synchronize the floating ingredients panel with the main ingredients list
function syncFloatingIngredientsPanel(root) {
  const mainList = root.querySelector("#legacyIngredientsList");
  const floatList = document.querySelector(".floating-ingredients-list");
  if (!mainList || !floatList) return;
  floatList.innerHTML = mainList.innerHTML;
}

// Set up the ingredient calculator on the recipe detail page
function setupIngredientCalculator(root, recipeId, baseServings) {
  const servingsEl = document.getElementById("calcServings");
  const modeEl = document.getElementById("calcMode");
  const statusEl = document.getElementById("calcStatus");
  const pdfEl = document.getElementById("recipeExportPdf");
  if (!servingsEl || !modeEl) return;

  let debounceTimer = null;

  const apply = async () => {
    let servings = parseFloat(String(servingsEl.value).replace(",", "."));
    if (Number.isNaN(servings) || servings <= 0) {
      servings = baseServings;
      servingsEl.value = String(baseServings);
    }
    const mode = modeEl.value || "original";
    if (statusEl) statusEl.textContent = "Updating…";

    const params = new URLSearchParams();
    params.set("servings", String(servings));
    params.set("mode", mode);

    if (pdfEl) {
      const baseHref = pdfEl.getAttribute("href").split("?")[0];
      pdfEl.setAttribute("href", `${baseHref}?${params.toString()}`);
    }

    try {
      const res = await fetch(`/api/recipes/${recipeId}/ingredients-computed?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");

      const legacy = document.getElementById("legacyIngredientsList");
      if (legacy && Array.isArray(data.legacyIngredientLines)) {
        legacy.innerHTML = data.legacyIngredientLines
          .map((line) => `<li>${escapeHtml(line)}</li>`)
          .join("");
      }

      if (Array.isArray(data.steps)) {
        data.steps.forEach((stepPayload, idx) => {
          if (!stepPayload || !stepPayload.ingredients) return;
          const ul = root.querySelector(`.js-step-ingredients[data-step-index="${idx}"]`);
          if (!ul) return;
          ul.innerHTML = stepPayload.ingredients
            .map((item) => `<li>${escapeHtml(formatComputedIngredientLine(item))}</li>`)
            .join("");
        });
      }

      syncFloatingIngredientsPanel(root);
      if (statusEl) statusEl.textContent = "";
    } catch (e) {
      if (statusEl) statusEl.textContent = "Could not update amounts.";
    }
  };

  const schedule = () => {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(apply, 280);
  };

  servingsEl.addEventListener("input", schedule);
  servingsEl.addEventListener("change", schedule);
  modeEl.addEventListener("change", schedule);
}

// Initialize the recipe detail page with like/favorite buttons, comments, and ingredient calculator
async function initRecipeDetail({ recipeId, baseServings = 1, enableIngredientCalc = false }) {
  const root = document.querySelector(".recipe-detail");
  if (!root) return;

  const likeBtn = root.querySelector(".js-like");
  const favBtn = root.querySelector(".js-fav");

  if (likeBtn) {
    likeBtn.addEventListener("click", async () => {
      likeBtn.disabled = true;
      try {
        const res = await apiFetch(`/api/recipes/${recipeId}/like`, { method: "POST", body: "{}" });
        const data = await res.json();
        if (res.ok) {
          likeBtn.dataset.liked = data.liked ? "1" : "0";
          root.querySelector(".js-like-text").textContent = data.liked ? "Liked" : "Like";
          root.querySelector(".js-like-count").textContent = String(data.likesCount);
        }
      } finally {
        likeBtn.disabled = false;
      }
    });
  }

  if (favBtn) {
    favBtn.addEventListener("click", async () => {
      favBtn.disabled = true;
      try {
        const res = await apiFetch(`/api/recipes/${recipeId}/favorite`, { method: "POST", body: "{}" });
        const data = await res.json();
        if (res.ok) {
          favBtn.dataset.favorited = data.favorited ? "1" : "0";
          root.querySelector(".js-fav-text").textContent = data.favorited ? "Favourited" : "Favourite";
        }
      } finally {
        favBtn.disabled = false;
      }
    });
  }

  const listEl = document.getElementById("commentsList");
  const bodyEl = document.getElementById("commentBody");
  const sendBtn = document.getElementById("sendComment");

  const renderComments = (comments) => {
    listEl.innerHTML = "";
    if (!comments.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "No comments yet.";
      listEl.appendChild(empty);
      return;
    }

    comments.forEach((c) => {
      const card = document.createElement("div");
      card.className = "comment";

      const top = document.createElement("div");
      top.className = "comment-top";

      const author = document.createElement("div");
      author.innerHTML = `<b>${escapeHtml(c.author)}</b> <span class="muted small">${new Date(c.createdAt).toLocaleString()}</span>`;
      top.appendChild(author);

      if (c.canDelete) {
        const del = document.createElement("button");
        del.className = "icon-btn";
        del.textContent = "Delete";
        del.addEventListener("click", async () => {
          if (!confirm("Delete comment?")) return;
          const res = await apiFetch(`/api/comments/${c.id}`, { method: "DELETE", body: "{}" });
          if (res.ok) loadComments();
        });
        top.appendChild(del);
      }

      const body = document.createElement("div");
      body.className = "comment-body";
      body.textContent = c.body;

      card.appendChild(top);
      card.appendChild(body);
      listEl.appendChild(card);
    });
  };

  const loadComments = async () => {
    const res = await fetch(`/api/recipes/${recipeId}/comments`);
    const data = await res.json();
    if (res.ok) renderComments(data.comments || []);
  };

  if (sendBtn) {
    sendBtn.addEventListener("click", async () => {
      const body = (bodyEl.value || "").trim();
      if (!body) return;
      sendBtn.disabled = true;
      try {
        const res = await apiFetch(`/api/recipes/${recipeId}/comments`, {
          method: "POST",
          body: JSON.stringify({ body })
        });
        if (res.ok) {
          bodyEl.value = "";
          await loadComments();
        }
      } finally {
        sendBtn.disabled = false;
      }
    });
  }

  await loadComments();

  if (enableIngredientCalc) {
    setupIngredientCalculator(root, recipeId, baseServings);
  }

  setupFloatingIngredients(root);
}

// Set up a floating ingredients panel
function setupFloatingIngredients(root) {
  const ingredientsSection = root.querySelector(".ingredients-section");
  const sourceList = ingredientsSection?.querySelector(".ingredients-list");
  if (!ingredientsSection || !sourceList || !sourceList.children.length) return;

  const floatEl = document.createElement("aside");
  floatEl.className = "floating-ingredients";
  floatEl.setAttribute("aria-label", "Ingredients");
  floatEl.setAttribute("aria-hidden", "true");

  const inner = document.createElement("div");
  inner.className = "floating-ingredients-inner card";

  const title = document.createElement("h3");
  title.className = "floating-ingredients-title";
  title.textContent = "Ingredients";

  const ul = document.createElement("ul");
  ul.className = "list ingredients-list floating-ingredients-list";
  for (const li of sourceList.children) {
    ul.appendChild(li.cloneNode(true));
  }

  inner.appendChild(title);
  inner.appendChild(ul);
  floatEl.appendChild(inner);
  document.body.appendChild(floatEl);

  const setVisible = (visible) => {
    floatEl.classList.toggle("is-visible", visible);
    floatEl.setAttribute("aria-hidden", visible ? "false" : "true");
  };

  const io = new IntersectionObserver(
    ([entry]) => {
      if (!entry) return;
      if (entry.isIntersecting) {
        setVisible(false);
        return;
      }
      const pastSection = entry.boundingClientRect.top < 0;
      setVisible(pastSection);
    },
    { threshold: 0, rootMargin: "0px" }
  );
  io.observe(ingredientsSection);
}

function escapeHtml(s) {
  return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

window.setupDynamicList = setupDynamicList;
window.setupIngredientEditor = setupIngredientEditor;
window.setupStepEditor = setupStepEditor;
window.initRecipeDetail = initRecipeDetail;
window.isSupportedImageFile = isSupportedImageFile;
window.isSupportedVideoFile = isSupportedVideoFile;
