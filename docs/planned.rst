Planned features and ideas
==========================
A consolidated wishlist of features and ideas for :mod:`flycastsim`.  The
project is developed in an ad-hoc fashion as time and motivation permit, so
this page is an **evolving backlog**, not a roadmap with dates.  Some items are
small extensions of existing modules; others are larger research directions.

Contributions and suggestions are welcome — open an issue or pull request on
`GitHub <https://github.com/grunde73/flycastsim>`_.

Rod characterisation
------------------------------
Extending the :mod:`flycastsim.rod` module beyond swingweight toward a fuller
data-driven rod description.

* **Mass distribution from MOI.**  Invert the swingweight calculation to
  estimate the rod's linear mass density :math:`\mu(x)` along its length, using
  the measured per-section moments of inertia — the complement of the current
  butt-axis MOI estimate.
* **Stiffness (EI) profile from static bend tests.**  Fit measured static
  bend curves under a *known* bending force / tip load to estimate the rod's
  bending-stiffness (EI) taper, giving a measured stiffness profile to feed the
  continuum engine instead of a tabulated guess.
* **Broader rod parameters.**  Derived quantities such as rod action, balance
  point and recommended line weight, built on the mass and stiffness profiles
  above.

Tackle modelling
------------------------------
Richer, data-driven tackle so the simulated line behaves more realistically.

* **Line and leader taper support.**  First-class tapered mass/diameter
  profiles for fly lines and leaders (head, belly, running line; leader steps),
  driving the component profiles used by the continuum engine.
* **Distinct leader + fly subdomains.**  Model the leader and fly as their own
  coupled subdomains so the line can unroll into a crisp, realistic loop.
* **Spherical-fly terminal boundary condition.**  A terminal point mass + drag
  at the line tip (the fly), the boundary condition still scaffolded in
  :mod:`flycastsim.fem`.

Casting dynamics & measurement
------------------------------
Closing the loop between real casts and the simulation.

* **Hand force and torque outputs.**  Compute the net force and torque the
  caster applies at the rod butt (the hand load) through the stroke — a key
  quantity for understanding casting effort and technique.
* **Work done by the caster.**  Integrate the hand force/torque against the
  rod-butt motion over the stroke to get the total mechanical work the caster
  puts into the cast — a direct measure of casting effort and a counterpart to
  the per-component energy outputs below.
* **Hauling.**  Support a *haul*: the caster pulling the line with the free
  (line) hand during the stroke to add line speed, coupled into the line
  subdomain.
* **Video extraction and import of caster motion.**  Extract the hand path and
  the rod angle / rotation / motion from high-speed footage and import them to
  drive the simulation directly from a real cast (replacing the hand-fitted
  angle sweep used today).
* **Full quantitative cast model.**  A tuned, validated cast model whose
  outputs match high-speed footage quantitatively, not just qualitatively.

Outputs & tooling
------------------------------
Getting data and insight out of the simulator.

* **Export of simulated data.**  Save simulated trajectories, line shapes and
  derived quantities to common formats (e.g. CSV) for external analysis.
* **Energy and work outputs.**  Compute the energy and work balances of the
  continuum model (the paper's energy/work relations), useful for diagnosing
  loading, release and efficiency.
* **Per-component energy breakdown.**  Track how energy is distributed across
  the different components/subdomains (rod, line, leader, fly) over the stroke
  — kinetic, elastic (bending/tension) and gravitational potential energy per
  component — to see where energy is stored and transferred during loading and
  release.
