(function () {
  const STORAGE_KEY = "macroTrackerStaticV1";
  const FOOD_REFERENCES = [
    { name: "Chicken Breast", aliases: ["chicken breast", "grilled chicken", "chicken"], caloriesPerGram: 1.65, proteinPerGram: 0.31, carbsPerGram: 0, fatPerGram: 0.036, gramsByUnit: { serving: 120, piece: 120, oz: 28.35 } },
    { name: "Ground Beef 90/10", aliases: ["ground beef", "lean beef", "beef"], caloriesPerGram: 1.76, proteinPerGram: 0.26, carbsPerGram: 0, fatPerGram: 0.1, gramsByUnit: { serving: 113, oz: 28.35 } },
    { name: "Salmon", aliases: ["salmon", "fish"], caloriesPerGram: 2.08, proteinPerGram: 0.2, carbsPerGram: 0, fatPerGram: 0.13, gramsByUnit: { serving: 113, oz: 28.35 } },
    { name: "White Rice", aliases: ["white rice", "rice"], caloriesPerGram: 1.3, proteinPerGram: 0.027, carbsPerGram: 0.282, fatPerGram: 0.003, gramsByUnit: { cup: 158, serving: 158, oz: 28.35 } },
    { name: "Brown Rice", aliases: ["brown rice"], caloriesPerGram: 1.23, proteinPerGram: 0.026, carbsPerGram: 0.255, fatPerGram: 0.01, gramsByUnit: { cup: 195, serving: 195, oz: 28.35 } },
    { name: "Cooked Pasta", aliases: ["pasta", "spaghetti", "penne", "macaroni"], caloriesPerGram: 1.58, proteinPerGram: 0.058, carbsPerGram: 0.306, fatPerGram: 0.009, gramsByUnit: { cup: 140, serving: 140, oz: 28.35 } },
    { name: "Oats", aliases: ["oats", "oatmeal"], caloriesPerGram: 3.89, proteinPerGram: 0.169, carbsPerGram: 0.663, fatPerGram: 0.069, gramsByUnit: { cup: 80, serving: 40, oz: 28.35 } },
    { name: "Banana", aliases: ["banana"], caloriesPerGram: 0.89, proteinPerGram: 0.011, carbsPerGram: 0.228, fatPerGram: 0.003, gramsByUnit: { banana: 118, piece: 118, serving: 118 } },
    { name: "Egg", aliases: ["egg", "eggs"], caloriesPerGram: 1.43, proteinPerGram: 0.126, carbsPerGram: 0.007, fatPerGram: 0.095, gramsByUnit: { egg: 50, piece: 50, serving: 50 } },
    { name: "Greek Yogurt", aliases: ["greek yogurt", "yogurt"], caloriesPerGram: 0.97, proteinPerGram: 0.1, carbsPerGram: 0.036, fatPerGram: 0.04, gramsByUnit: { cup: 245, serving: 170, oz: 28.35 } },
    { name: "Peanut Butter", aliases: ["peanut butter"], caloriesPerGram: 5.88, proteinPerGram: 0.25, carbsPerGram: 0.2, fatPerGram: 0.5, gramsByUnit: { tbsp: 16, serving: 32, oz: 28.35 } },
    { name: "Potato", aliases: ["potato", "potatoes"], caloriesPerGram: 0.77, proteinPerGram: 0.02, carbsPerGram: 0.17, fatPerGram: 0.001, gramsByUnit: { potato: 173, piece: 173, cup: 150 } },
    { name: "Avocado", aliases: ["avocado"], caloriesPerGram: 1.6, proteinPerGram: 0.02, carbsPerGram: 0.085, fatPerGram: 0.147, gramsByUnit: { avocado: 150, piece: 150, serving: 50 } },
    { name: "Bread", aliases: ["bread", "toast"], caloriesPerGram: 2.65, proteinPerGram: 0.09, carbsPerGram: 0.49, fatPerGram: 0.032, gramsByUnit: { slice: 28, piece: 28, serving: 28 } },
    { name: "Milk", aliases: ["milk"], caloriesPerGram: 0.61, proteinPerGram: 0.032, carbsPerGram: 0.048, fatPerGram: 0.033, gramsByUnit: { cup: 244, serving: 244 } },
    { name: "Protein Bar", aliases: ["protein bar", "bar"], caloriesPerGram: 3.83, proteinPerGram: 0.33, carbsPerGram: 0.4, fatPerGram: 0.117, gramsByUnit: { bar: 60, piece: 60, serving: 60 } }
  ];

  const UNIT_ALIASES = {
    g: "g", gram: "g", grams: "g", kg: "kg", oz: "oz", ounce: "oz", ounces: "oz", lb: "lb", lbs: "lb", pound: "lb", pounds: "lb",
    cup: "cup", cups: "cup", tbsp: "tbsp", tablespoon: "tbsp", tablespoons: "tbsp", tsp: "tsp", teaspoon: "tsp", teaspoons: "tsp",
    slice: "slice", slices: "slice", piece: "piece", pieces: "piece", serving: "serving", servings: "serving", banana: "banana", bananas: "banana",
    apple: "apple", apples: "apple", egg: "egg", eggs: "egg", bar: "bar", bars: "bar", potato: "potato", potatoes: "potato", avocado: "avocado", avocados: "avocado"
  };

  const CALORIE_REGEX = /(\d+(?:\.\d+)?)\s*(?:k?cal|calories?|cals?)\b/i;
  const AMOUNT_REGEX = /(\d+(?:\.\d+)?)\s*(g|grams?|kg|oz|ounces?|lbs?|pounds?|cups?|tbsp|tablespoons?|tsp|teaspoons?|slices?|pieces?|servings?|bananas?|apples?|eggs?|bars?|potatoes?|avocados?)\b/i;

  const defaultState = () => ({
    version: 1,
    selectedDate: todayISO(),
    settings: {
      dailyCalories: 2200,
      dailyProtein: 150,
      dailyCarbs: 200,
      dailyFat: 65,
      defaultBurned: 2600
    },
    burned: {},
    entries: {},
    savedMeals: [],
    libraryItems: []
  });

  const state = loadState();
  let activeScreen = "dashboard";
  let activeRestaurant = window.FAST_FOOD_RESTAURANTS?.[0]?.slug || "";
  let currentEstimate = null;
  let currentPhotoFile = null;
  let toastTimer = null;

  const els = {
    appTitle: document.querySelector(".app-title"),
    headerDateLabel: document.getElementById("headerDateLabel"),
    selectedDate: document.getElementById("selectedDate"),
    caloriesConsumedValue: document.getElementById("caloriesConsumedValue"),
    caloriesGoalValue: document.getElementById("caloriesGoalValue"),
    calorieRing: document.getElementById("calorieRing"),
    dailyDeficitValue: document.getElementById("dailyDeficitValue"),
    dailyBurnValue: document.getElementById("dailyBurnValue"),
    remainingCaloriesValue: document.getElementById("remainingCaloriesValue"),
    proteinValue: document.getElementById("proteinValue"),
    fatValue: document.getElementById("fatValue"),
    carbsValue: document.getElementById("carbsValue"),
    proteinGoalValue: document.getElementById("proteinGoalValue"),
    fatGoalValue: document.getElementById("fatGoalValue"),
    carbsGoalValue: document.getElementById("carbsGoalValue"),
    proteinTrack: document.getElementById("proteinTrack"),
    fatTrack: document.getElementById("fatTrack"),
    carbsTrack: document.getElementById("carbsTrack"),
    weeklyChart: document.getElementById("weeklyChart"),
    weeklyDeficitTotal: document.getElementById("weeklyDeficitTotal"),
    weeklyNutritionValue: document.getElementById("weeklyNutritionValue"),
    weeklyBurnedTotal: document.getElementById("weeklyBurnedTotal"),
    weeklyDifferenceValue: document.getElementById("weeklyDifferenceValue"),
    foodLogHeading: document.getElementById("foodLogHeading"),
    foodLogList: document.getElementById("foodLogList"),
    libraryItemsList: document.getElementById("libraryItemsList"),
    savedMealsList: document.getElementById("savedMealsList"),
    restaurantTabs: document.getElementById("restaurantTabs"),
    fastFoodSearchInput: document.getElementById("fastFoodSearchInput"),
    fastFoodServingInput: document.getElementById("fastFoodServingInput"),
    fastFoodItemsList: document.getElementById("fastFoodItemsList"),
    describeInput: document.getElementById("describeInput"),
    knownCaloriesInput: document.getElementById("knownCaloriesInput"),
    estimateFoodButton: document.getElementById("estimateFoodButton"),
    takePhotoButton: document.getElementById("takePhotoButton"),
    choosePhotoButton: document.getElementById("choosePhotoButton"),
    cameraCaptureInput: document.getElementById("cameraCaptureInput"),
    photoPickerInput: document.getElementById("photoPickerInput"),
    selectedPhotoLabel: document.getElementById("selectedPhotoLabel"),
    scanNameInput: document.getElementById("scanNameInput"),
    scanBrandInput: document.getElementById("scanBrandInput"),
    scanLabelButton: document.getElementById("scanLabelButton"),
    ocrTextOutput: document.getElementById("ocrTextOutput"),
    manualNameInput: document.getElementById("manualNameInput"),
    manualCaloriesInput: document.getElementById("manualCaloriesInput"),
    manualProteinInput: document.getElementById("manualProteinInput"),
    manualCarbsInput: document.getElementById("manualCarbsInput"),
    manualFatInput: document.getElementById("manualFatInput"),
    manualAddButton: document.getElementById("manualAddButton"),
    estimateSourcePill: document.getElementById("estimateSourcePill"),
    editorName: document.getElementById("editorName"),
    editorBrand: document.getElementById("editorBrand"),
    editorAmount: document.getElementById("editorAmount"),
    editorUnit: document.getElementById("editorUnit"),
    editorCalories: document.getElementById("editorCalories"),
    editorProtein: document.getElementById("editorProtein"),
    editorCarbs: document.getElementById("editorCarbs"),
    editorFat: document.getElementById("editorFat"),
    editorNotes: document.getElementById("editorNotes"),
    addEstimateToLogButton: document.getElementById("addEstimateToLogButton"),
    saveEstimateMealButton: document.getElementById("saveEstimateMealButton"),
    archiveEstimateItemButton: document.getElementById("archiveEstimateItemButton"),
    goalCaloriesInput: document.getElementById("goalCaloriesInput"),
    goalProteinInput: document.getElementById("goalProteinInput"),
    goalCarbsInput: document.getElementById("goalCarbsInput"),
    goalFatInput: document.getElementById("goalFatInput"),
    goalBurnedInput: document.getElementById("goalBurnedInput"),
    dayBurnedInput: document.getElementById("dayBurnedInput"),
    saveGoalsButton: document.getElementById("saveGoalsButton"),
    exportStateButton: document.getElementById("exportStateButton"),
    toast: document.getElementById("toast")
  };

  init();

  function init() {
    els.selectedDate.value = state.selectedDate;
    bindEvents();
    renderAll();
  }

  function bindEvents() {
    document.querySelectorAll("[data-screen-target]").forEach((button) => {
      button.addEventListener("click", () => switchScreen(button.dataset.screenTarget));
    });

    document.querySelectorAll("[data-assistant-tab]").forEach((button) => {
      button.addEventListener("click", () => switchAssistantTab(button.dataset.assistantTab));
    });

    els.selectedDate.addEventListener("change", () => {
      state.selectedDate = els.selectedDate.value || todayISO();
      persist();
      renderAll();
    });

    els.fastFoodSearchInput.addEventListener("input", renderFastFood);
    els.estimateFoodButton.addEventListener("click", handleEstimateText);
    els.takePhotoButton.addEventListener("click", () => els.cameraCaptureInput.click());
    els.choosePhotoButton.addEventListener("click", () => els.photoPickerInput.click());
    els.cameraCaptureInput.addEventListener("change", () => updatePhotoSelection("camera"));
    els.photoPickerInput.addEventListener("change", () => updatePhotoSelection("picker"));
    els.scanLabelButton.addEventListener("click", handleScanLabel);
    els.manualAddButton.addEventListener("click", handleManualAdd);
    els.addEstimateToLogButton.addEventListener("click", handleAddEstimateToLog);
    els.saveEstimateMealButton.addEventListener("click", handleSaveEstimateMeal);
    els.archiveEstimateItemButton.addEventListener("click", handleArchiveEstimateItem);
    els.saveGoalsButton.addEventListener("click", handleSaveGoals);
    els.exportStateButton.addEventListener("click", handleExportBackup);

    els.fastFoodItemsList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-fast-food-id]");
      if (!button) return;
      const restaurant = window.FAST_FOOD_RESTAURANTS.find((item) => item.slug === activeRestaurant);
      const food = restaurant?.items.find((item) => item.id === button.dataset.fastFoodId);
      if (!food) return;
      const servings = positiveNumber(els.fastFoodServingInput.value, 1);
      addEntry({
        name: `${food.name} (${food.serving_label})`,
        calories: round(food.calories * servings),
        protein_g: round(food.protein_g * servings),
        carbs_g: round(food.carbs_g * servings),
        fat_g: round(food.fat_g * servings),
        source: "fast_food",
        notes: `${restaurant.name} · ${food.category}`,
        servings
      });
      showToast("Fast-food item added.");
    });

    els.restaurantTabs.addEventListener("click", (event) => {
      const button = event.target.closest("[data-restaurant-slug]");
      if (!button) return;
      activeRestaurant = button.dataset.restaurantSlug;
      renderFastFood();
    });

    els.libraryItemsList.addEventListener("click", (event) => handleListActions(event, "library"));
    els.savedMealsList.addEventListener("click", (event) => handleListActions(event, "saved"));
    els.foodLogList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-delete-entry]");
      if (!button) return;
      deleteEntry(button.dataset.deleteEntry);
      showToast("Food log removed.");
    });
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultState();
      const parsed = JSON.parse(raw);
      return {
        ...defaultState(),
        ...parsed,
        settings: { ...defaultState().settings, ...(parsed.settings || {}) },
        burned: parsed.burned || {},
        entries: parsed.entries || {},
        savedMeals: parsed.savedMeals || [],
        libraryItems: parsed.libraryItems || []
      };
    } catch {
      return defaultState();
    }
  }

  function persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function switchScreen(screen) {
    activeScreen = screen;
    document.querySelectorAll(".screen").forEach((node) => node.classList.toggle("screen--active", node.dataset.screen === screen));
    document.querySelectorAll("[data-screen-target]").forEach((button) => button.classList.toggle("is-active", button.dataset.screenTarget === screen));
    const titles = {
      dashboard: "Dashboard",
      library: "Library",
      assistant: "Add Food",
      "fast-food": "Fast Food",
      goals: "Goals"
    };
    els.appTitle.textContent = titles[screen] || "Macro Tracker";
  }

  function switchAssistantTab(tab) {
    document.querySelectorAll("[data-assistant-tab]").forEach((button) => button.classList.toggle("is-active", button.dataset.assistantTab === tab));
    document.querySelectorAll("[data-assistant-pane]").forEach((pane) => pane.classList.toggle("assistant-pane--active", pane.dataset.assistantPane === tab));
  }

  function renderAll() {
    renderHeader();
    renderDashboard();
    renderLibrary();
    renderFastFood();
    renderGoals();
  }

  function renderHeader() {
    const date = new Date(`${state.selectedDate}T12:00:00`);
    els.headerDateLabel.textContent = date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
  }

  function renderDashboard() {
    const day = getDayData(state.selectedDate);
    const settings = state.settings;
    const calorieProgress = clamp(day.calories / Math.max(settings.dailyCalories, 1), 0, 1.25);
    const proteinProgress = clamp(day.protein_g / Math.max(settings.dailyProtein, 1), 0, 1.25);
    const deficitProgress = clamp(day.deficit / Math.max(settings.defaultBurned, 1), 0, 1.25);

    els.caloriesConsumedValue.textContent = formatNumber(day.calories);
    els.caloriesGoalValue.textContent = `of ${formatNumber(settings.dailyCalories)} kcal`;
    els.dailyDeficitValue.textContent = `${signedNumber(day.deficit)} kcal`;
    els.dailyBurnValue.textContent = `${formatNumber(day.burned)} kcal`;
    els.remainingCaloriesValue.textContent = `${formatNumber(settings.dailyCalories - day.calories)} kcal`;
    els.proteinValue.textContent = `${formatNumber(day.protein_g)} g`;
    els.fatValue.textContent = `${formatNumber(day.fat_g)} g`;
    els.carbsValue.textContent = `${formatNumber(day.carbs_g)} g`;
    els.proteinGoalValue.textContent = `Goal: ${formatNumber(settings.dailyProtein)} g`;
    els.fatGoalValue.textContent = `Goal: ${formatNumber(settings.dailyFat)} g`;
    els.carbsGoalValue.textContent = `Goal: ${formatNumber(settings.dailyCarbs)} g`;
    els.proteinTrack.style.width = `${Math.min(100, proteinProgress * 100)}%`;
    els.fatTrack.style.width = `${Math.min(100, clamp(day.fat_g / Math.max(settings.dailyFat, 1), 0, 1.25) * 100)}%`;
    els.carbsTrack.style.width = `${Math.min(100, clamp(day.carbs_g / Math.max(settings.dailyCarbs, 1), 0, 1.25) * 100)}%`;
    els.calorieRing.style.setProperty("--calorie-progress", `${calorieProgress}turn`);
    els.calorieRing.style.setProperty("--protein-progress", `${proteinProgress}turn`);
    els.calorieRing.style.setProperty("--deficit-progress", `${Math.max(0.08, Math.abs(deficitProgress))}turn`);

    renderWeekly(day);
    renderFoodLog(day.entries);
  }

  function renderWeekly(day) {
    const week = getWeekData(state.selectedDate);
    els.weeklyChart.innerHTML = week.map((entry) => {
      const calorieHeight = Math.min(100, (entry.calories / Math.max(state.settings.dailyCalories * 1.15, 1)) * 100);
      const burnedHeight = Math.min(100, (entry.burned / Math.max(state.settings.defaultBurned * 1.15, 1)) * 100);
      const label = new Date(`${entry.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 1);
      return `
        <div class="week-day">
          <div class="week-day__bars">
            <span class="week-day__nutrition" style="height:${calorieHeight}%"></span>
            <span class="week-day__burned" style="height:${burnedHeight}%"></span>
          </div>
          <span class="week-day__label">${label}</span>
          <span class="week-day__delta">${signedNumber(entry.deficit)}</span>
        </div>
      `;
    }).join("");

    const totalCalories = week.reduce((sum, item) => sum + item.calories, 0);
    const totalBurned = week.reduce((sum, item) => sum + item.burned, 0);
    const totalDeficit = week.reduce((sum, item) => sum + item.deficit, 0);

    els.weeklyDeficitTotal.textContent = `${signedNumber(totalDeficit)} kcal`;
    els.weeklyNutritionValue.textContent = `${formatNumber(totalCalories)} kcal`;
    els.weeklyBurnedTotal.textContent = `${formatNumber(totalBurned)} kcal`;
    els.weeklyDifferenceValue.textContent = `${signedNumber(totalDeficit)} kcal`;
  }

  function renderFoodLog(entries) {
    els.foodLogHeading.textContent = `${entries.length} food logs`;
    if (!entries.length) {
      els.foodLogList.innerHTML = emptyState("No meals logged yet", "Use Add Food, Fast Food, or your library to start filling the day.");
      return;
    }

    els.foodLogList.innerHTML = entries.map((entry) => foodItemTemplate(entry, true)).join("");
  }

  function renderLibrary() {
    if (!state.libraryItems.length) {
      els.libraryItemsList.innerHTML = emptyState("No archived items yet", "Scan a nutrition label or save a grocery item and it will live here.");
    } else {
      els.libraryItemsList.innerHTML = state.libraryItems.map((item) => foodItemTemplate(item, false, "library")).join("");
    }

    if (!state.savedMeals.length) {
      els.savedMealsList.innerHTML = emptyState("No saved meals yet", "Save a reusable meal from the Add Food screen.");
    } else {
      els.savedMealsList.innerHTML = state.savedMeals.map((meal) => foodItemTemplate(meal, false, "saved")).join("");
    }
  }

  function renderFastFood() {
    const restaurants = window.FAST_FOOD_RESTAURANTS || [];
    if (!restaurants.length) {
      els.restaurantTabs.innerHTML = "";
      els.fastFoodItemsList.innerHTML = emptyState("No fast-food catalog", "Catalog data is missing.");
      return;
    }

    if (!activeRestaurant || !restaurants.some((restaurant) => restaurant.slug === activeRestaurant)) {
      activeRestaurant = restaurants[0].slug;
    }

    els.restaurantTabs.innerHTML = restaurants.map((restaurant) => `
      <button class="restaurant-tab ${restaurant.slug === activeRestaurant ? "is-active" : ""}" type="button" data-restaurant-slug="${restaurant.slug}">
        ${escapeHtml(restaurant.name)}
      </button>
    `).join("");

    const restaurant = restaurants.find((item) => item.slug === activeRestaurant);
    const search = (els.fastFoodSearchInput.value || "").trim().toLowerCase();
    const items = restaurant.items.filter((item) => {
      const haystack = `${item.name} ${item.category} ${item.serving_label}`.toLowerCase();
      return !search || haystack.includes(search);
    });

    if (!items.length) {
      els.fastFoodItemsList.innerHTML = emptyState("No matches", "Try a different search or another restaurant tab.");
      return;
    }

    els.fastFoodItemsList.innerHTML = items.map((item) => `
      <article class="food-item">
        <div class="food-item__header">
          <div>
            <h3>${escapeHtml(item.name)}</h3>
            <p class="food-item__meta">${escapeHtml(item.category)} · ${escapeHtml(item.serving_label)}</p>
          </div>
          <span class="pill">${formatNumber(item.calories)} kcal</span>
        </div>
        <div class="food-item__macro-grid">
          <div><span>Protein</span><strong>${formatNumber(item.protein_g)} g</strong></div>
          <div><span>Carbs</span><strong>${formatNumber(item.carbs_g)} g</strong></div>
          <div><span>Fat</span><strong>${formatNumber(item.fat_g)} g</strong></div>
          <div><span>Source</span><strong>${escapeHtml(restaurant.name)}</strong></div>
        </div>
        <button class="action-button" type="button" data-fast-food-id="${item.id}">Add to log</button>
      </article>
    `).join("");
  }

  function renderGoals() {
    els.goalCaloriesInput.value = state.settings.dailyCalories;
    els.goalProteinInput.value = state.settings.dailyProtein;
    els.goalCarbsInput.value = state.settings.dailyCarbs;
    els.goalFatInput.value = state.settings.dailyFat;
    els.goalBurnedInput.value = state.settings.defaultBurned;
    els.dayBurnedInput.value = getBurnedForDate(state.selectedDate);
  }

  function handleEstimateText() {
    const query = (els.describeInput.value || "").trim();
    if (!query) {
      showToast("Describe the food first.", true);
      return;
    }
    const estimate = estimateFromText(query, els.knownCaloriesInput.value);
    populateEstimateEditor(estimate);
    showToast("Estimate ready.");
  }

  async function handleScanLabel() {
    if (!currentPhotoFile) {
      showToast("Choose or take a nutrition label photo first.", true);
      return;
    }
    if (!window.Tesseract) {
      showToast("OCR library did not load.", true);
      return;
    }

    els.scanLabelButton.disabled = true;
    els.scanLabelButton.textContent = "Reading label...";
    try {
      const result = await window.Tesseract.recognize(currentPhotoFile, "eng");
      const text = result.data.text || "";
      els.ocrTextOutput.textContent = text || "No OCR text returned.";
      const estimate = parseNutritionLabelText(text, els.scanNameInput.value, els.scanBrandInput.value);
      estimate.ocrText = text;
      populateEstimateEditor(estimate);
      showToast("Label scanned.");
    } catch (error) {
      showToast(error?.message || "Label scan failed.", true);
    } finally {
      els.scanLabelButton.disabled = false;
      els.scanLabelButton.textContent = "Read label";
    }
  }

  function handleManualAdd() {
    const name = (els.manualNameInput.value || "").trim();
    if (!name) {
      showToast("Give the food a name.", true);
      return;
    }
    addEntry({
      name,
      calories: numberOrZero(els.manualCaloriesInput.value),
      protein_g: numberOrZero(els.manualProteinInput.value),
      carbs_g: numberOrZero(els.manualCarbsInput.value),
      fat_g: numberOrZero(els.manualFatInput.value),
      source: "manual"
    });
    els.manualNameInput.value = "";
    els.manualCaloriesInput.value = "";
    els.manualProteinInput.value = "";
    els.manualCarbsInput.value = "";
    els.manualFatInput.value = "";
    showToast("Meal added.");
  }

  function handleAddEstimateToLog() {
    const estimate = readEstimateEditor();
    if (!estimate.name) {
      showToast("Nothing to add yet.", true);
      return;
    }
    addEntry(estimate);
    showToast("Estimate added to log.");
  }

  function handleSaveEstimateMeal() {
    const estimate = readEstimateEditor();
    if (!estimate.name) {
      showToast("Nothing to save yet.", true);
      return;
    }
    state.savedMeals.unshift({
      id: uid("meal"),
      ...estimate
    });
    persist();
    renderLibrary();
    showToast("Saved as reusable meal.");
  }

  function handleArchiveEstimateItem() {
    const estimate = readEstimateEditor();
    if (!estimate.name) {
      showToast("Nothing to archive yet.", true);
      return;
    }
    state.libraryItems.unshift({
      id: uid("item"),
      ...estimate
    });
    persist();
    renderLibrary();
    showToast("Archived in My Foods.");
  }

  function handleSaveGoals() {
    state.settings.dailyCalories = positiveNumber(els.goalCaloriesInput.value, 2200);
    state.settings.dailyProtein = positiveNumber(els.goalProteinInput.value, 150);
    state.settings.dailyCarbs = positiveNumber(els.goalCarbsInput.value, 200);
    state.settings.dailyFat = positiveNumber(els.goalFatInput.value, 65);
    state.settings.defaultBurned = positiveNumber(els.goalBurnedInput.value, 2600);
    state.burned[state.selectedDate] = positiveNumber(els.dayBurnedInput.value, state.settings.defaultBurned);
    persist();
    renderAll();
    showToast("Goals updated.");
  }

  function handleExportBackup() {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `macro-tracker-backup-${todayISO()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    showToast("Backup exported.");
  }

  function updatePhotoSelection(source) {
    if (source === "camera") {
      els.photoPickerInput.value = "";
      currentPhotoFile = els.cameraCaptureInput.files[0] || null;
    } else {
      els.cameraCaptureInput.value = "";
      currentPhotoFile = els.photoPickerInput.files[0] || null;
    }
    els.selectedPhotoLabel.textContent = currentPhotoFile ? currentPhotoFile.name : "No image selected yet.";
  }

  function handleListActions(event, type) {
    const logButton = event.target.closest("[data-log-item]");
    if (logButton) {
      const list = type === "library" ? state.libraryItems : state.savedMeals;
      const item = list.find((entry) => entry.id === logButton.dataset.logItem);
      if (!item) return;
      addEntry({ ...item, source: type === "library" ? "library_item" : "saved_meal" });
      showToast(type === "library" ? "Archived item logged." : "Saved meal logged.");
      return;
    }

    const deleteButton = event.target.closest("[data-delete-item]");
    if (!deleteButton) return;
    if (type === "library") {
      state.libraryItems = state.libraryItems.filter((item) => item.id !== deleteButton.dataset.deleteItem);
    } else {
      state.savedMeals = state.savedMeals.filter((item) => item.id !== deleteButton.dataset.deleteItem);
    }
    persist();
    renderLibrary();
    showToast("Removed.");
  }

  function addEntry(entry) {
    const normalized = {
      id: uid("entry"),
      name: entry.name,
      brand: entry.brand || "",
      amount: positiveNumber(entry.amount || entry.serving_amount, 1),
      unit: entry.unit || entry.serving_unit || "serving",
      calories: round(numberOrZero(entry.calories)),
      protein_g: round(numberOrZero(entry.protein_g)),
      carbs_g: round(numberOrZero(entry.carbs_g)),
      fat_g: round(numberOrZero(entry.fat_g)),
      notes: entry.notes || "",
      source: entry.source || "manual",
      createdAt: new Date().toISOString()
    };
    state.entries[state.selectedDate] = [normalized, ...(state.entries[state.selectedDate] || [])];
    persist();
    renderAll();
  }

  function deleteEntry(id) {
    state.entries[state.selectedDate] = (state.entries[state.selectedDate] || []).filter((entry) => entry.id !== id);
    persist();
    renderAll();
  }

  function getDayData(date) {
    const entries = [...(state.entries[date] || [])];
    const totals = entries.reduce((acc, entry) => {
      acc.calories += numberOrZero(entry.calories);
      acc.protein_g += numberOrZero(entry.protein_g);
      acc.carbs_g += numberOrZero(entry.carbs_g);
      acc.fat_g += numberOrZero(entry.fat_g);
      return acc;
    }, { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 });
    const burned = getBurnedForDate(date);
    return {
      entries,
      calories: round(totals.calories),
      protein_g: round(totals.protein_g),
      carbs_g: round(totals.carbs_g),
      fat_g: round(totals.fat_g),
      burned,
      deficit: round(burned - totals.calories)
    };
  }

  function getWeekData(date) {
    const base = new Date(`${date}T12:00:00`);
    return Array.from({ length: 7 }, (_, index) => {
      const target = new Date(base);
      target.setDate(base.getDate() - (6 - index));
      const key = target.toISOString().slice(0, 10);
      const day = getDayData(key);
      return { date: key, ...day };
    });
  }

  function getBurnedForDate(date) {
    return round(numberOrZero(state.burned[date], state.settings.defaultBurned));
  }

  function foodItemTemplate(item, allowDelete, mode = "entry") {
    const title = `${item.brand ? `${item.brand} · ` : ""}${item.name}`;
    const noteLine = [item.notes, item.unit ? `${formatNumber(item.amount || 1)} ${item.unit}` : ""].filter(Boolean).join(" · ");
    const actions = mode === "entry"
      ? `<button class="ghost-button" type="button" data-delete-entry="${item.id}">Delete</button>`
      : `
        <div class="inline-row">
          <button class="action-button" type="button" data-log-item="${item.id}">Log</button>
          <button class="ghost-button" type="button" data-delete-item="${item.id}">Delete</button>
        </div>
      `;

    return `
      <article class="food-item">
        <div class="food-item__header">
          <div>
            <h3>${escapeHtml(title)}</h3>
            <p class="food-item__meta">${escapeHtml(noteLine || (item.source || "manual").replaceAll("_", " "))}</p>
          </div>
          <span class="pill">${formatNumber(item.calories)} kcal</span>
        </div>
        <div class="food-item__macro-grid">
          <div><span>Protein</span><strong>${formatNumber(item.protein_g)} g</strong></div>
          <div><span>Fat</span><strong>${formatNumber(item.fat_g)} g</strong></div>
          <div><span>Carbs</span><strong>${formatNumber(item.carbs_g)} g</strong></div>
          <div><span>Source</span><strong>${escapeHtml((item.source || "manual").replaceAll("_", " "))}</strong></div>
        </div>
        ${actions}
      </article>
    `;
  }

  function emptyState(title, copy) {
    return `<article class="empty-state"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p></article>`;
  }

  function populateEstimateEditor(estimate) {
    currentEstimate = estimate;
    els.estimateSourcePill.textContent = estimate.source ? estimate.source.replaceAll("_", " ") : "Estimate";
    els.editorName.value = estimate.name || "";
    els.editorBrand.value = estimate.brand || "";
    els.editorAmount.value = positiveNumber(estimate.serving_amount, 1);
    els.editorUnit.value = estimate.serving_unit || "serving";
    els.editorCalories.value = numberOrZero(estimate.calories);
    els.editorProtein.value = numberOrZero(estimate.protein_g);
    els.editorCarbs.value = numberOrZero(estimate.carbs_g);
    els.editorFat.value = numberOrZero(estimate.fat_g);
    els.editorNotes.value = estimate.notes || "";
  }

  function readEstimateEditor() {
    return {
      name: (els.editorName.value || "").trim(),
      brand: (els.editorBrand.value || "").trim(),
      serving_amount: positiveNumber(els.editorAmount.value, 1),
      serving_unit: (els.editorUnit.value || "serving").trim(),
      calories: numberOrZero(els.editorCalories.value),
      protein_g: numberOrZero(els.editorProtein.value),
      carbs_g: numberOrZero(els.editorCarbs.value),
      fat_g: numberOrZero(els.editorFat.value),
      notes: (els.editorNotes.value || "").trim(),
      source: currentEstimate?.source || "assistant_text"
    };
  }

  function estimateFromText(query, knownCaloriesValue) {
    const lowered = query.toLowerCase();
    const explicitCalories = numberOrNull(knownCaloriesValue) ?? extractNumber(lowered, CALORIE_REGEX);
    const amountMatch = lowered.match(AMOUNT_REGEX);
    const amount = amountMatch ? Number(amountMatch[1]) : 1;
    const unit = amountMatch ? (UNIT_ALIASES[amountMatch[2]] || "serving") : "serving";
    const reference = FOOD_REFERENCES.find((item) => item.aliases.some((alias) => lowered.includes(alias)));
    const cleanName = query
      .replace(CALORIE_REGEX, "")
      .replace(AMOUNT_REGEX, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^[,.-]+|[,.-]+$/g, "");

    if (!reference) {
      return {
        name: cleanName || "Custom food",
        serving_amount: amount,
        serving_unit: unit,
        calories: round(explicitCalories || 0),
        protein_g: 0,
        carbs_g: 0,
        fat_g: 0,
        notes: "No strong food match yet. Edit the values before saving if needed.",
        source: "assistant_text"
      };
    }

    const grams = gramsFor(reference, amount, unit);
    let calories = grams * reference.caloriesPerGram;
    let protein = grams * reference.proteinPerGram;
    let carbs = grams * reference.carbsPerGram;
    let fat = grams * reference.fatPerGram;
    let notes = `Estimated from ${amount} ${unit} of ${reference.name.toLowerCase()}.`;

    if (explicitCalories && calories > 0) {
      const scale = explicitCalories / calories;
      calories = explicitCalories;
      protein *= scale;
      carbs *= scale;
      fat *= scale;
      notes = `Matched ${reference.name.toLowerCase()} and scaled macros to your provided calories.`;
    }

    return {
      name: reference.name,
      serving_amount: amount,
      serving_unit: unit,
      calories: round(calories),
      protein_g: round(protein),
      carbs_g: round(carbs),
      fat_g: round(fat),
      notes,
      source: "assistant_text"
    };
  }

  function parseNutritionLabelText(text, fallbackName, fallbackBrand) {
    const normalized = String(text || "");
    const lines = normalized.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const servingLabel = extractText(normalized, [/serving size[:\s]+([^\n]+)/i]) || "1 serving";
    const calories = extractValue(normalized, [/\bcalories\b[:\s]+(\d+(?:\.\d+)?)/i, /\bcalories\s+(\d+(?:\.\d+)?)/i]);
    const protein = extractValue(normalized, [/\bprotein\b[:\s]+(\d+(?:\.\d+)?)/i]);
    const carbs = extractValue(normalized, [/\btotal carbohydrate[s]?\b[:\s]+(\d+(?:\.\d+)?)/i, /\bcarb[s]?\b[:\s]+(\d+(?:\.\d+)?)/i]);
    const fat = extractValue(normalized, [/\btotal fat\b[:\s]+(\d+(?:\.\d+)?)/i, /\bfat\b[:\s]+(\d+(?:\.\d+)?)/i]);
    const titleCandidate = lines.find((line) => !/nutrition|serving|calories/i.test(line) && line.length < 60) || "Scanned Item";
    return {
      name: (fallbackName || titleCandidate).trim(),
      brand: (fallbackBrand || "").trim(),
      serving_amount: 1,
      serving_unit: "serving",
      calories: round(calories),
      protein_g: round(protein),
      carbs_g: round(carbs),
      fat_g: round(fat),
      notes: `Parsed from nutrition label. Serving size: ${servingLabel}.`,
      source: "label_scan"
    };
  }

  function gramsFor(reference, amount, unit) {
    if (unit === "g") return amount;
    if (unit === "kg") return amount * 1000;
    if (unit === "oz") return amount * 28.35;
    if (unit === "lb") return amount * 453.592;
    if (unit === "tbsp") return amount * (reference.gramsByUnit.tbsp || 15);
    if (unit === "tsp") return amount * (reference.gramsByUnit.tsp || 5);
    return amount * (reference.gramsByUnit[unit] || reference.gramsByUnit.serving || 100);
  }

  function extractValue(text, regexes) {
    for (const regex of regexes) {
      const match = text.match(regex);
      if (match) return Number(match[1]);
    }
    return 0;
  }

  function extractText(text, regexes) {
    for (const regex of regexes) {
      const match = text.match(regex);
      if (match) return match[1].trim();
    }
    return "";
  }

  function extractNumber(text, regex) {
    const match = text.match(regex);
    return match ? Number(match[1]) : null;
  }

  function todayISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function uid(prefix) {
    return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
  }

  function round(value) {
    return Math.round((Number(value) || 0) * 10) / 10;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value || 0));
  }

  function positiveNumber(value, fallback) {
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
  }

  function numberOrZero(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function numberOrNull(value) {
    if (value === "" || value === null || value === undefined) return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }

  function formatNumber(value) {
    const numeric = Number(value || 0);
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, "");
  }

  function signedNumber(value) {
    const numeric = round(value);
    return `${numeric > 0 ? "+" : ""}${formatNumber(numeric)}`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function showToast(message, isError = false) {
    els.toast.textContent = message;
    els.toast.classList.toggle("is-error", Boolean(isError));
    els.toast.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      els.toast.classList.remove("show");
    }, 2600);
  }
})();
