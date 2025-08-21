# models/account_move.py
from odoo import models, fields
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'

    loan_manager_id = fields.Many2one('loan.manager.loan', string='Préstamo', copy=False, readonly=True)

    def write(self, vals):
        if 'loan_manager_id' in vals:
            raise ValidationError("No se puede cambiar el préstamo asociado desde el asiento contable.")
        return super().write(vals)

    def action_open_loan_from_move(self):
        self.ensure_one()
        if not self.loan_manager_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'loan.manager.loan',
            'view_mode': 'form',
            'res_id': self.loan_manager_id.id,
        }