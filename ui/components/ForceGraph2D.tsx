"use client";

import type { ComponentType } from "react";
import fromKapsule from "react-kapsule";
import ForceGraph2DKapsule from "force-graph";

// react-kapsule expects a Kapsule factory shape; force-graph runtime matches this API.
// @ts-expect-error force-graph typings don't expose the kapsule call signature directly.
const ForceGraph2D = fromKapsule(ForceGraph2DKapsule, {
  methodNames: [
    "emitParticle",
    "d3Force",
    "d3ReheatSimulation",
    "stopAnimation",
    "pauseAnimation",
    "resumeAnimation",
    "centerAt",
    "zoom",
    "zoomToFit",
    "getGraphBbox",
    "screen2GraphCoords",
    "graph2ScreenCoords",
  ],
}) as ComponentType<Record<string, unknown>>;

export default ForceGraph2D;
