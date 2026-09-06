export default {
  extends: ["stylelint-config-standard"],
  ignoreFiles: ["src/generated/**"],
  rules: {
    "color-no-hex": true,
    "declaration-property-value-disallowed-list": {
      "border-radius": ["/([3-9]|[1-9][0-9]+)px/"],
      "background-image": ["/gradient/"],
      "backdrop-filter": [/.+/],
    },
    "selector-class-pattern": null,
    "custom-property-pattern": null,
  },
};
