# Team 17: The Anti-Smoking Campaigners - Slide Deck Guide
As requested in your assignment, you need to submit a 5-slide PDF named `Team-17.pdf`. Use the Streamlit application we just built to capture the necessary screenshots and fill in the details for your presentation.

Here is the exact structure for your slides, optimized for your 5-minute concise presentation:

### Slide 1: The MVP Demo
* **Visual:** Take a screenshot of **Tab 1: Billboard Priority Ranking**. Make sure the Top 10 filter is applied and both the Table and the Bar Chart are visible. Include a screenshot of the **Sidebar** showing the "Top Recommended Counties".
* **Talking Points:** "Our primary task was to strategically place billboards where they’d be seen by the most *active* smokers. We pulled live tract-level CDC PLACES data via Socrata, aggregated it to the county level, and calculated a **Priority Score** (Prevalence % × Population). These top counties are where our budget goes."

### Slide 2: Visual Grammar Defense
* **Visual:** Take screenshots of the **State Drill Down Map (Tab 2)** and the **Priority Score Bar Chart (Tab 1)**.
* **Text / Justification:** 
  * "We used choropleth maps (color intensity as the primary channel) to visually isolate geographic clusters of high prevalence, ensuring we identify regional hotspots effortlessly."
  * "For exact comparisons, we utilized bar charts with Position/Length as marks. This is the most accurate visual tool to contrast strictly numerical figures like the Priority Score."
* **Talking Points:** "We chose absolute length for scoring and color shading for geographic density, ensuring our agency clients can immediately spot where to buy billboard space."

### Slide 3: The "Phase 2" Demo (Entrepreneurial Expansion)
* **Visual:** Take a screenshot of **Tab 4: Phase 2: Health ROI**. Show the Scatter Plot of COPD vs Smoking, and the High-Risk Targeting Matrix. 
* **Talking Points:** "For Phase 2, we thought like entrepreneurs. Knowing where smokers are is great, but targeting areas where smoking heavily correlates with severe health outcomes like **COPD** maximizes our public health ROI. We pulled an additional COPD dataset from the CDC and cross-referenced it. Our campaign will now target the most heavily afflicted 'high-risk' counties shown here."

### Slide 4: AI Integration (Defined)
* **Visual:** A simple flowchart or bulleted list defining the AI role. You can optionally include a screenshot of the "Methodology & AI Strategy" expander at the bottom of the dashboard.
* **Text / Talking Points:** 
  * *Current Use:* "We utilized Generative AI to accelerate data ingestion, build API queries with the `sodapy` library, and craft Streamlit/Plotly boilerplate visualizations."
  * *Future Role:* "We plan to implement an AI/ML predictive layer pointing API data towards Social Vulnerability indices, and build an embedded LLM 'Chatbot' allowing our marketing team to ask: *'Where do we drop our $100K budget?'* and get instant data-backed answers."

### Slide 5: Sprint to Final
* **Visual:** A timeline or roadmap graphic.
* **Text / Talking Points:** 
  * **What's left to code:** Integrating the actual LLM API endpoint (e.g., OpenAI or DeepSeek) deeply into the dashboard chat interface, and wrapping up predictive caching to speed up data loads.
  * **Polishing the UI:** Refining color themes, enhancing Map tooltip interactivity, and making the dashboard fully mobile-responsive so teams can use it in the field.
