# Application and Deployment Contract

## User-facing sections

The Streamlit app exposes three primary sections:

1. **Simple 1-D model**: configurable spring stiffness, brick mass, car speed,
   turn and stop times; selectable plots; optional reference comparison,
   event markers, and animation.
2. **Sample fly cast / Cast #1**: line weight, rod, rod stiffness scale, mesh
   size, drag/damping, display settings, and explicit simulation launch.
3. **Rod parameters**: swingweight input/calculation, bundled/session rod
   comparison, and rod upload/form tracing and fitting.

The precise controls and ranges are enumerated in the baseline spec. Long
computations must be explicitly launched, report progress/errors, and reuse
eligible cached results. Changing only a display-only measurement location
must not recompute Cast #1.

## Public availability and deployment events

- The app is publicly reachable through its hosted Streamlit URL.
- Pull requests targeting `main` run validation or preview work without
  replacing the public app.
- A merge into `main` publishes the updated public app.
- Documentation publication is a separate GitHub Pages workflow.
- Deployment credentials and platform-specific settings are supplied by the
  hosting environment; secrets must not be committed.

The exact preview mechanism and hosting-task configuration are deployment
details, not a new public API contract. CI must report failures rather than
publishing an apparently successful result after failed validation.

## Resource and user-data behavior

No numeric uptime, concurrency, or latency guarantee is part of the product.
Large rod fits may be slow and animation behavior may depend on bandwidth.
There is no explicit product-level maximum archive size or frame count;
hosting environment limits apply.

Uploaded rod data and reusable fits may be held in shared temporary storage
and reused across sessions. The product does not guarantee a retention
period.
