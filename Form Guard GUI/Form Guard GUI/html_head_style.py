html_head_style = '''
<style>
    /* page background + hide scrollbar */
    html, body {
        margin: 0;
        padding: 0;
        background-color: #111827;
        color: white;
        height: 100%;
        width: 100%;
        scrollbar-width: none;
        -ms-overflow-style: none;
    }
    body::-webkit-scrollbar { display: none; }

    /* exit button */
    .exit-btn {
        background-color: #c30000 !important;
        color: #000 !important;
        border: 2px solid #080B12 !important;
        width: 1.5rem !important;
        height: 1rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* containers */
    .container-style {
        border: 4px solid #080B12 !important;
        box-shadow: 0 0 20px 4px rgba(59,130,246,0.3) !important;
        padding: 2rem 2rem !important;
    }

    /* plot container */
    .plot-style {
        border: 4px solid #080B12 !important;
        box-shadow: 0 0 20px 4px rgba(59,130,246,0.3) !important;
    }

    /* button-like select + regular buttons */
    .light-btn {
        background-color: #5898d4 !important;
        color: #fff !important;
        border: 4px solid #080B12 !important;
        border-radius: 1rem !important;
        box-shadow: 0 0 20px 4px rgba(59,130,246,0.3) !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease-in-out !important;
        min-width: 10rem !important;
        max-width: 30rem !important;
    }

    .active-btn {
        background-color: #214D94 !important;
        color: #C2C2C2 !important;
        border: 4px solid #111827 !important;
        box-shadow: 0 0 25px 5px rgba(59,130,246,0.5) !important;
    }

    .light-btn .q-field__control {
        min-height: 2.75rem;
        display: flex;
        align-items: center;
        padding-left: 0.8rem !important;
        padding-right: 0.4rem !important;
    }

    .light-btn .q-field__label {
        color: rgba(255,255,255,0.9) !important;
        font-weight: 600;
    }

    /* force selected/combo text to stay white */
    .light-btn .q-field__native,
    .light-btn input {
        background: transparent !important;
        color: #ffffff !important;
    }

    /* focus state for select/button */
    .light-btn.q-field--focused {
        box-shadow: 0 0 25px 6px rgba(59,130,246,0.45) !important;
        background-color: #214D94 !important;
    }

    /* dropdown/popup global styling */
    .q-menu,
    .q-popup {
        background-color: #0b1220 !important;
        color: #fff !important;
        border-radius: 0.5rem !important;
        box-shadow: 0 8px 30px rgba(0,0,0,0.6) !important;
        z-index: 9999 !important;
    }

    .q-menu .q-list .q-item,
    .q-popup .q-list .q-item {
        background-color: transparent !important;
        color: #fff !important;
    }

    /* highlight for hover + selected items */
    .q-item:hover,
    .q-item.q-item--active,
    .q-item.q-item--selected {
        background-color: rgba(88,152,212,0.18) !important;
        color: #ffffff !important;
    }
                 
    /* radio buttons */
    .btn-radios {
        display: inline-flex;
        gap: 0.4rem;
        align-items: center;
    }

    .btn-radios .q-radio {
        flex: 1 1 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.45rem 1rem;
        border-radius: 1rem;
        border: 4px solid #080B12;
        background-color: #5898d4;
        color: #fff;
        font-weight: 600;
        font-size: 1rem;
        box-shadow: 0 0 20px 4px rgba(59,130,246,0.3);
        transition: all 0.16s ease-in-out;
        cursor: pointer;
        white-space: nowrap;
        min-width: 0;
        position: relative;
    }

    /* hide native radio circles */
    .btn-radios .q-radio__inner,
    .btn-radios .q-radio__bg {
        display: none !important;
    }

    /* label styling */
    .btn-radios .q-radio__label {
        width: 100%;
        text-align: center;
        color: inherit;
        margin: 0;
        z-index: 1;
        pointer-events: none;
        line-height: 1.2;
    }

    /* hover + focus */
    .btn-radios .q-radio:hover {
        box-shadow: 0 0 26px 5px rgba(59,130,246,0.22);
        transform: translateY(-1px);
    }
    .btn-radios .q-radio:focus-within {
        box-shadow: 0 0 30px 6px rgba(59,130,246,0.45);
        outline: none;
    }

    /* checked (active) state */
    .btn-radios .q-radio.q-radio--checked,
    .btn-radios .q-radio.q-radio--active,
    .btn-radios .q-radio[aria-checked="true"] {
        background-color: #214D94 !important;
        color: #C2C2C2 !important;
        border-color: #111827 !important;
        box-shadow: 0 0 25px 5px rgba(59,130,246,0.5) !important;
    }

    .btn-radios .q-radio.q-radio--checked .q-radio__label {
        color: #C2C2C2 !important;
    }

    /* labels */


    .custom-label {
        display: inline-block;
        background-color: #0b1220 !important;
        color: #ffffff !important;
        border: 3px solid #080B12 !important;
        border-radius: 0.75rem !important;
        padding: 0.4rem 1rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        letter-spacing: 0.3px !important;
        transition: all 0.2s ease-in-out !important;
        text-align: center !important;
        min-width: 6rem;
    }

    .custom-label.success {
        background-color: #1B5E20 !important;
        box-shadow: 0 0 20px 4px rgba(16,185,129,0.45) !important;
    }

    .custom-label.warning {
        background-color: #78350F !important;
        box-shadow: 0 0 20px 4px rgba(245,158,11,0.45) !important;
    }

    .custom-label.error {
        background-color: #7F1D1D !important;
        box-shadow: 0 0 20px 4px rgba(239,68,68,0.45) !important;
    }
    
    .custom-label-large-text {
        font-size: 2rem !important;
    }

    /* Toast / ui.notify styling */
    .q-notification {
        background-color: #0b1220 !important; /* dark panel */
        color: #ffffff !important;
        border: 3px solid #080B12 !important;
        border-radius: 0.75rem !important;
        box-shadow: 0 0 22px 5px rgba(59,130,246,0.45) !important;
        padding: 0.9rem 1.4rem !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        letter-spacing: 0.3px !important;
        max-width: 24rem !important;
    }

    /* icon inside toast */
    .q-notification__icon {
        color: #3B82F6 !important; /* match your accent blue */
    }

    /* message text */
    .q-notification__message {
        color: #ffffff !important;
    }

    /* success / warning / error color glow */
    .q-notification.bg-positive {
        background-color: #1B5E20 !important;
        box-shadow: 0 0 20px 4px rgba(16,185,129,0.45) !important;
    }

    .q-notification.bg-warning {
        background-color: #78350F !important;
        box-shadow: 0 0 20px 4px rgba(245,158,11,0.45) !important;
    }

    .q-notification.bg-negative {
        background-color: #7F1D1D !important;
        box-shadow: 0 0 20px 4px rgba(239,68,68,0.45) !important;
    }

    /* Close button (X) */
    .q-notification__close {
        color: #ffffff !important;
        opacity: 0.8;
        transition: 0.15s ease-in-out;
    }

    .q-notification__close:hover {
        opacity: 1;
        transform: scale(1.2);
    }
</style>
'''