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
    apple: "apple", apples: "apple", egg: "egg", eggs: "egg", bar: "bar", bars: "bar", potato: "potato", potatoes: "potato", avocado: "avocado", avocados: "avocado",
    scoop: "scoop", scoops: "scoop", bottle: "bottle", bottles: "bottle", container: "container", containers: "container", bowl: "bowl", bowls: "bowl"
  };

  const CALORIE_REGEX = /(\d+(?:\.\d+)?)\s*(?:k?cal|calories?|cals?)\b/i;
  const AMOUNT_REGEX = /(\d+(?:\.\d+)?)\s*(g|grams?|kg|oz|ounces?|lbs?|pounds?|cups?|tbsp|tablespoons?|tsp|teaspoons?|slices?|pieces?|servings?|bananas?|apples?|eggs?|bars?|potatoes?|avocados?|scoops?|bottles?|containers?|bowls?)\b/i;

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
  let currentLibraryEdit = null;
  let toastTimer = null;

  const els = {
    appTitle: document.querySelector(".app-title"),
    headerDateLabel: document.getElementById("headerDateLabel"),
    selectedDate: document.getElementById("selectedDate"),
    caloriesConsumedValue: document.getElementById("caloriesConsumedValue"),
    ringProteinValue: document.getElementById("ringProteinValue"),
    ringFatValue: document.getElementById("ringFatValue"),
    ringCarbsValue: document.getElementById("ringCarbsValue"),
    caloriesGoalValue: document.getElementById("caloriesGoalValue"),
    calorieRing: document.getElementById("calorieRing"),
    dailyDeficitValue: document.getElementById("dailyDeficitValue"),
    dailyBurnValue: document.getElementById("dailyBurnValue"),
    remainingCaloriesValue: document.getElementById("remainingCaloriesValue"),
    dashboardBurnInput: document.getElementById("dashboardBurnInput"),
    saveDashboardBurnButton: document.getElementById("saveDashboardBurnButton"),
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
    librarySearchInput: document.getElementById("librarySearchInput"),
    librarySearchStatus: document.getElementById("librarySearchStatus"),
    libraryItemsList: document.getElementById("libraryItemsList"),
    savedMealsList: document.getElementById("savedMealsList"),
    libraryEditorPanel: document.getElementById("libraryEditorPanel"),
    libraryEditorHeading: document.getElementById("libraryEditorHeading"),
    libraryEditorType: document.getElementById("libraryEditorType"),
    libraryEditorName: document.getElementById("libraryEditorName"),
    libraryEditorBrand: document.getElementById("libraryEditorBrand"),
    libraryEditorAmount: document.getElementById("libraryEditorAmount"),
    libraryEditorUnit: document.getElementById("libraryEditorUnit"),
    libraryEditorCalories: document.getElementById("libraryEditorCalories"),
    libraryEditorProtein: document.getElementById("libraryEditorProtein"),
    libraryEditorCarbs: document.getElementById("libraryEditorCarbs"),
    libraryEditorFat: document.getElementById("libraryEditorFat"),
    libraryEditorNotes: document.getElementById("libraryEditorNotes"),
    saveLibraryEditButton: document.getElementById("saveLibraryEditButton"),
    cancelLibraryEditButton: document.getElementById("cancelLibraryEditButton"),
    restaurantTabs: document.getElementById("restaurantTabs"),
    fastFoodSearchInput: document.getElementById("fastFoodSearchInput"),
    fastFoodServingInput: document.getElementById("fastFoodServingInput"),
    fastFoodItemsList: document.getElementById("fastFoodItemsList"),
    describeInput: document.getElementById("describeInput"),
    assistantConversation: document.getElementById("assistantConversation"),
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
    els.librarySearchInput.addEventListener("input", renderLibrary);
    els.saveDashboardBurnButton.addEventListener("click", handleSaveDashboardBurn);
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
    els.saveLibraryEditButton.addEventListener("click", handleSaveLibraryEdit);
    els.cancelLibraryEditButton.addEventListener("click", closeLibraryEditor);

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
    const fatProgress = clamp(day.fat_g / Math.max(settings.dailyFat, 1), 0, 1.25);
    const carbsProgress = clamp(day.carbs_g / Math.max(settings.dailyCarbs, 1), 0, 1.25);

    els.caloriesConsumedValue.textContent = formatNumber(day.calories);
    els.ringProteinValue.textContent = formatNumber(day.protein_g);
    els.ringFatValue.textContent = formatNumber(day.fat_g);
    els.ringCarbsValue.textContent = formatNumber(day.carbs_g);
    els.caloriesGoalValue.textContent = `${formatNumber(settings.dailyCalories)} kcal goal`;
    els.dailyDeficitValue.textContent = `${signedNumber(day.deficit)} kcal`;
    els.dailyBurnValue.textContent = `${formatNumber(day.burned)} kcal`;
    els.remainingCaloriesValue.textContent = `${formatNumber(settings.dailyCalories - day.calories)} kcal`;
    els.dashboardBurnInput.value = formatNumber(day.burned);
    els.proteinValue.textContent = `${formatNumber(day.protein_g)} g`;
    els.fatValue.textContent = `${formatNumber(day.fat_g)} g`;
    els.carbsValue.textContent = `${formatNumber(day.carbs_g)} g`;
    els.proteinGoalValue.textContent = `Goal: ${formatNumber(settings.dailyProtein)} g`;
    els.fatGoalValue.textContent = `Goal: ${formatNumber(settings.dailyFat)} g`;
    els.carbsGoalValue.textContent = `Goal: ${formatNumber(settings.dailyCarbs)} g`;
    els.proteinTrack.style.width = `${Math.min(100, proteinProgress * 100)}%`;
    els.fatTrack.style.width = `${Math.min(100, fatProgress * 100)}%`;
    els.carbsTrack.style.width = `${Math.min(100, carbsProgress * 100)}%`;
    renderMacroRing(calorieProgress, proteinProgress, fatProgress, carbsProgress);

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
    const search = (els.librarySearchInput.value || "").trim().toLowerCase();
    els.libraryEditorPanel.classList.toggle("editor-panel--hidden", !currentLibraryEdit);

    const libraryItems = state.libraryItems.filter((item) => matchesLibrarySearch(item, search));
    const savedMeals = state.savedMeals.filter((meal) => matchesLibrarySearch(meal, search));
    const totalVisible = libraryItems.length + savedMeals.length;
    const totalItems = state.libraryItems.length + state.savedMeals.length;

    els.librarySearchStatus.textContent = search
      ? `${totalVisible} result${totalVisible === 1 ? "" : "s"} for "${els.librarySearchInput.value.trim()}".`
      : "Showing everything in your library.";

    if (!state.libraryItems.length) {
      els.libraryItemsList.innerHTML = emptyState("No archived items yet", "Scan a nutrition label or save a grocery item and it will live here.");
    } else if (!libraryItems.length) {
      els.libraryItemsList.innerHTML = emptyState("No archived item matches", "Try a different search.");
    } else {
      els.libraryItemsList.innerHTML = libraryItems.map((item) => foodItemTemplate(item, false, "library")).join("");
    }

    if (!state.savedMeals.length) {
      els.savedMealsList.innerHTML = emptyState("No saved meals yet", "Save a reusable meal from the Add Food screen.");
    } else if (!savedMeals.length) {
      els.savedMealsList.innerHTML = emptyState("No saved meal matches", "Try a different search.");
    } else {
      els.savedMealsList.innerHTML = savedMeals.map((meal) => foodItemTemplate(meal, false, "saved")).join("");
    }

    if (!totalItems) {
      els.librarySearchStatus.textContent = "Your library is empty.";
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
    appendChatMessage("user", query);
    const estimate = estimateFromText(query, els.knownCaloriesInput.value);
    populateEstimateEditor(estimate);
    appendChatMessage("assistant", estimate.assistant_message || estimate.notes || "Estimate ready.");
    showToast("Estimate ready.");
  }

  function handleSaveDashboardBurn() {
    state.burned[state.selectedDate] = positiveNumber(els.dashboardBurnInput.value, state.settings.defaultBurned);
    persist();
    renderAll();
    showToast("Daily calories burned updated.");
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
      appendChatMessage("user", `Scan label${els.scanNameInput.value ? ` for ${els.scanNameInput.value}` : ""}.`);
      appendChatMessage("assistant", estimate.assistant_message || estimate.notes || "Label scanned.");
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
    const editButton = event.target.closest("[data-edit-item]");
    if (editButton) {
      openLibraryEditor(type, editButton.dataset.editItem);
      return;
    }

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

  function openLibraryEditor(type, id) {
    const list = type === "library" ? state.libraryItems : state.savedMeals;
    const item = list.find((entry) => entry.id === id);
    if (!item) return;

    currentLibraryEdit = { type, id };
    els.libraryEditorHeading.textContent = type === "library" ? "Edit archived item" : "Edit saved meal";
    els.libraryEditorType.textContent = type === "library" ? "Archived item" : "Saved meal";
    els.libraryEditorName.value = item.name || "";
    els.libraryEditorBrand.value = item.brand || "";
    els.libraryEditorAmount.value = positiveNumber(item.amount || item.serving_amount, 1);
    els.libraryEditorUnit.value = item.unit || item.serving_unit || "serving";
    els.libraryEditorCalories.value = numberOrZero(item.calories);
    els.libraryEditorProtein.value = numberOrZero(item.protein_g);
    els.libraryEditorCarbs.value = numberOrZero(item.carbs_g);
    els.libraryEditorFat.value = numberOrZero(item.fat_g);
    els.libraryEditorNotes.value = item.notes || "";
    renderLibrary();
    els.libraryEditorPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function closeLibraryEditor() {
    currentLibraryEdit = null;
    renderLibrary();
  }

  function handleSaveLibraryEdit() {
    if (!currentLibraryEdit) return;
    const editType = currentLibraryEdit.type;
    const listKey = editType === "library" ? "libraryItems" : "savedMeals";
    const list = state[listKey];
    const item = list.find((entry) => entry.id === currentLibraryEdit.id);
    if (!item) return;

    item.name = (els.libraryEditorName.value || "").trim();
    item.brand = (els.libraryEditorBrand.value || "").trim();
    item.amount = positiveNumber(els.libraryEditorAmount.value, 1);
    item.serving_amount = item.amount;
    item.unit = (els.libraryEditorUnit.value || "serving").trim();
    item.serving_unit = item.unit;
    item.calories = round(numberOrZero(els.libraryEditorCalories.value));
    item.protein_g = round(numberOrZero(els.libraryEditorProtein.value));
    item.carbs_g = round(numberOrZero(els.libraryEditorCarbs.value));
    item.fat_g = round(numberOrZero(els.libraryEditorFat.value));
    item.notes = (els.libraryEditorNotes.value || "").trim();

    persist();
    closeLibraryEditor();
    renderAll();
    showToast(editType === "library" ? "Archived item updated." : "Saved meal updated.");
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

  function renderMacroRing(calories, protein, fat, carbs) {
    const segments = [
      ["var(--gold)", calories],
      ["var(--pink)", protein],
      ["var(--mint)", fat],
      ["var(--blue)", carbs]
    ];
    let start = 0;
    const parts = [];
    segments.forEach(([color, progress]) => {
      const end = start + 90;
      const filled = start + Math.min(1, progress) * 90;
      parts.push(`${color} ${start}deg ${filled}deg`);
      if (filled < end) {
        parts.push(`rgba(255,255,255,0.08) ${filled}deg ${end}deg`);
      }
      start = end;
    });
    els.calorieRing.style.background = `radial-gradient(circle at center, #050505 53%, transparent 54%), conic-gradient(${parts.join(", ")})`;
  }

  function matchesLibrarySearch(item, search) {
    if (!search) return true;
    const haystack = [
      item.name,
      item.brand,
      item.notes,
      item.source,
      item.unit,
      item.serving_unit,
      item.calories,
      item.protein_g,
      item.carbs_g,
      item.fat_g
    ].join(" ").toLowerCase();
    return haystack.includes(search);
  }

  function foodItemTemplate(item, allowDelete, mode = "entry") {
    const title = `${item.brand ? `${item.brand} · ` : ""}${item.name}`;
    const noteLine = [item.notes, item.unit ? `${formatNumber(item.amount || 1)} ${item.unit}` : ""].filter(Boolean).join(" · ");
    const actions = mode === "entry"
      ? `<button class="ghost-button" type="button" data-delete-entry="${item.id}">Delete</button>`
      : `
        <div class="inline-row">
          <button class="action-button" type="button" data-log-item="${item.id}">Log</button>
          <button class="ghost-button" type="button" data-edit-item="${item.id}">Edit</button>
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

  function appendChatMessage(role, message) {
    if (!els.assistantConversation) return;
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble chat-bubble--${role}`;
    bubble.innerHTML = `<p>${escapeHtml(message)}</p>`;
    els.assistantConversation.appendChild(bubble);
    els.assistantConversation.scrollTop = els.assistantConversation.scrollHeight;
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
    const matches = matchFoodReferences(lowered);
    const cleanName = query
      .replace(CALORIE_REGEX, "")
      .replace(AMOUNT_REGEX, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^[,.-]+|[,.-]+$/g, "");

    if (!matches.length) {
      return {
        name: cleanName || "Custom food",
        serving_amount: 1,
        serving_unit: "meal",
        calories: round(explicitCalories || 0),
        protein_g: 0,
        carbs_g: 0,
        fat_g: 0,
        notes: "No strong food match yet. Edit the values before saving if needed.",
        assistant_message: "I could not confidently match that meal to known foods yet. Add rough portions or calories for a better estimate.",
        source: "assistant_text"
      };
    }

    let calories = 0;
    let protein = 0;
    let carbs = 0;
    let fat = 0;
    const notes = [];
    matches.forEach(({ reference, amount, unit }) => {
      const grams = gramsFor(reference, amount, unit);
      calories += grams * reference.caloriesPerGram;
      protein += grams * reference.proteinPerGram;
      carbs += grams * reference.carbsPerGram;
      fat += grams * reference.fatPerGram;
      notes.push(`${formatNumber(amount)} ${unit} ${reference.name.toLowerCase()}`);
    });

    if (explicitCalories && calories > 0) {
      const scale = explicitCalories / calories;
      calories = explicitCalories;
      protein *= scale;
      carbs *= scale;
      fat *= scale;
    }

    return {
      name: cleanName || matches.map((match) => match.reference.name).join(" + "),
      serving_amount: 1,
      serving_unit: "meal",
      calories: round(calories),
      protein_g: round(protein),
      carbs_g: round(carbs),
      fat_g: round(fat),
      notes: explicitCalories
        ? `Matched ${notes.join(", ")} and scaled macros to your provided calories.`
        : `Estimated from ${notes.join(", ")}.`,
      assistant_message: explicitCalories
        ? `I matched ${notes.join(", ")} and scaled the macros to ${formatNumber(explicitCalories)} calories.`
        : `I estimated this as ${notes.join(", ")}.`,
      source: "assistant_text"
    };
  }

  function parseNutritionLabelText(text, fallbackName, fallbackBrand) {
    const normalized = normalizeOcrText(text);
    const lines = normalized.split(/\n+/).map((line) => line.trim()).filter(Boolean);
    const servingLabel = extractText(normalized, [/serving size[:\s]+([^\n]+)/i]) || "1 serving";
    let calories = extractCalories(lines, normalized);
    const protein = extractMacroFromLines(lines, ["protein"]);
    const carbs = extractMacroFromLines(lines, ["total carbohydrate", "total carbs", "carbohydrate", "carbs"]);
    const fat = extractMacroFromLines(lines, ["total fat", "fat"]);
    if (!calories && (protein || carbs || fat)) {
      calories = protein * 4 + carbs * 4 + fat * 9;
    }
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
      assistant_message: `I read the label as ${formatNumber(calories)} calories, ${formatNumber(protein)}g protein, ${formatNumber(carbs)}g carbs, and ${formatNumber(fat)}g fat.`,
      source: "label_scan"
    };
  }

  function matchFoodReferences(query) {
    const aliases = FOOD_REFERENCES
      .flatMap((reference) => reference.aliases.map((alias) => ({ alias, reference })))
      .sort((a, b) => b.alias.length - a.alias.length);
    const spans = [];
    const matches = [];
    aliases.forEach(({ alias, reference }) => {
      const index = query.indexOf(alias);
      if (index < 0) return;
      const span = [index, index + alias.length];
      if (spans.some((existing) => span[0] < existing[1] && existing[0] < span[1])) return;
      const { amount, unit } = amountNearAlias(query, span);
      spans.push(span);
      matches.push({ reference, amount, unit, index });
    });
    return matches.sort((a, b) => a.index - b.index);
  }

  function amountNearAlias(query, span) {
    const windowStart = Math.max(0, span[0] - 26);
    const windowEnd = Math.min(query.length, span[1] + 22);
    const windowText = query.slice(windowStart, windowEnd);
    const matches = [...windowText.matchAll(new RegExp(AMOUNT_REGEX.source, "gi"))];
    const candidate = matches.find((match) => {
      const start = windowStart + match.index;
      const end = start + match[0].length;
      return Math.min(Math.abs(end - span[0]), Math.abs(start - span[1])) <= 16;
    });
    if (!candidate) return { amount: 1, unit: "serving" };
    return {
      amount: Number(candidate[1]),
      unit: UNIT_ALIASES[candidate[2].toLowerCase()] || "serving"
    };
  }

  function normalizeOcrText(text) {
    return String(text || "")
      .replace(/\r/g, "\n")
      .replace(/\|/g, " ")
      .replace(/\bO(?=\d)/g, "0")
      .replace(/(\d)O\b/g, "$10")
      .replace(/\s+%/g, "%")
      .replace(/[ \t]+/g, " ")
      .trim();
  }

  function extractCalories(lines, normalized) {
    const direct = extractValue(normalized, [/\bcalories\b[:\s]+(\d+(?:\.\d+)?)/i, /\bcalories\s+(\d+(?:\.\d+)?)/i]);
    if (direct) return direct;
    const index = lines.findIndex((line) => /calories/i.test(line) && !/from fat/i.test(line));
    if (index < 0) return 0;
    return firstNumber(lines[index]) || firstNumber(lines[index + 1] || "") || 0;
  }

  function extractMacroFromLines(lines, aliases) {
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      if (!aliases.some((alias) => line.toLowerCase().includes(alias))) continue;
      const value = gramsFromLine(line, aliases);
      if (value !== null) return value;
      for (let offset = 1; offset <= 2; offset += 1) {
        const nextValue = gramsFromLine(lines[index + offset] || "", aliases);
        if (nextValue !== null) return nextValue;
      }
    }
    return 0;
  }

  function gramsFromLine(line, aliases) {
    const cleaned = String(line || "").replace(/\d+\s*%/g, "");
    const aliasPattern = aliases.map((alias) => alias.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
    const inline = cleaned.match(new RegExp(`(?:${aliasPattern})[^\\d]*(\\d+(?:\\.\\d+)?)\\s*g\\b`, "i"));
    if (inline) return Number(inline[1]);
    const grams = cleaned.match(/(\d+(?:\.\d+)?)\s*g\b/i);
    if (grams) return Number(grams[1]);
    if (aliases.some((alias) => cleaned.toLowerCase().includes(alias))) return firstNumber(cleaned);
    return null;
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

  function firstNumber(text) {
    const match = String(text || "").match(/(\d+(?:\.\d+)?)/);
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
