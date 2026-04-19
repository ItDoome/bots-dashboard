// React 18 DOM safety patch — must load BEFORE react-dom bundle.
// Prevents "Node.removeChild: not a child" crash caused by external
// code (Cloudflare, Telegram widget, browser translation, extensions)
// moving DOM nodes behind React's back.
// See: https://github.com/facebook/react/issues/11538
(function () {
  if (typeof Node === "undefined") return;

  var origRemoveChild = Node.prototype.removeChild;
  Node.prototype.removeChild = function (child) {
    if (child.parentNode !== this) {
      return child;
    }
    return origRemoveChild.apply(this, arguments);
  };

  var origInsertBefore = Node.prototype.insertBefore;
  Node.prototype.insertBefore = function (newNode, refNode) {
    if (refNode && refNode.parentNode !== this) {
      return origInsertBefore.call(this, newNode, null);
    }
    return origInsertBefore.apply(this, arguments);
  };
})();
