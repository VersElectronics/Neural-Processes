from torch import nn
import torch

from modules.latent_encoder import LatentEncoder
from modules.deterministic_encoder import DeterministicEncoder
from modules.decoder import Decoder 


class ANP_RNN_Model(nn.Module):
    """
    (Attentive) Neural Process model
    """
    def __init__(self,
                 x_dim,
                 y_dim,
                 mlp_hidden_size_list,
                 latent_dim,
                 use_rnn=True,
                 use_self_attention=True,
                 le_self_attention_type="dot",
                 de_self_attention_type="dot",
                 de_cross_attention_type="multihead",
                 use_deter_path=True,
                 **kwargs):
        super(ANP_RNN_Model, self).__init__()
        self.x_dim = x_dim
        self.y_dim = y_dim
        self.mlp_hidden_size_list = mlp_hidden_size_list
        self.latent_dim = latent_dim
        self.use_rnn = use_rnn
        self.use_deter_path = use_deter_path

        if self.use_rnn:
            self.x_dim = latent_dim
            self.num_rnn_layers = 2
            
            self.rnn = nn.LSTM(x_dim, self.x_dim, self.num_rnn_layers)
        else:
            self.rnn_hidden_size = None
            self.num_rnn_layers = None
            self.rnn = None

        # NOTICE: Latent Encoder
        self._latent_encoder = LatentEncoder(input_x_dim=self.x_dim,
                                             input_y_dim=self.y_dim,
                                             hidden_dim_list=self.mlp_hidden_size_list,
                                             latent_dim=self.latent_dim,
                                             use_self_attn=use_self_attention,
                                             self_attention_type=le_self_attention_type
                                             )
        # NOTICE : Decoder
        self._decoder = Decoder(x_dim=self.x_dim,
                                y_dim=self.y_dim,
                                mid_hidden_dim_list=self.mlp_hidden_size_list,
                                latent_dim=self.latent_dim,  # the dim of last axis of sc and z..
                                use_deterministic_path=True,  # whether use d_path or not will change the size of input
                                use_lstm=False
                                 )

        # NOTICE: Deterministic Encoder
        self._deter_encoder = DeterministicEncoder( input_x_dim=self.x_dim,
                                                    input_y_dim=self.y_dim,
                                                    hidden_dim_list=self.mlp_hidden_size_list,
                                                    latent_dim=self.latent_dim,  # the dim of last axis of r..
                                                    self_attention_type=de_self_attention_type,
                                                    use_self_attn=use_self_attention,
                                                    attention_layers=2,
                                                    use_lstm=False,
                                                    cross_attention_type=de_cross_attention_type,
                                                    attention_dropout=0)


    def forward(self, context_x, context_y, target_x, target_y=None):
        _, target_size, _ = target_x.size()

        # Transform context_x, target_x to latent sequence using LSTM.
        if self.use_rnn:
            _, context_size, _ = context_x.size()

            h0 = torch.randn(self.num_rnn_layers, context_size, self.x_dim)  # hidden states
            c0 = torch.randn(self.num_rnn_layers, context_size, self.x_dim)  # cell states
            context_x, _ = self.rnn(context_x, (h0, c0))
        
            h0 = torch.randn(self.num_rnn_layers, target_size, self.x_dim)  # hidden states
            c0 = torch.randn(self.num_rnn_layers, target_size, self.x_dim)  # cell states
            target_x, _ = self.rnn(target_x, (h0, c0))


        prior_dist, prior_mu, prior_sigma = self._latent_encoder(context_x, context_y)

        # For training, when target_y is available, use targets for latent encoder.
        # Note that targets contain contexts by design.
        # NOTICE: Here is the difference:
        #   Deepmind: latent_rep = prior/poster .sample()
        #   soobinseo: latent_rep = prior/poster
        #   3spring :  latent_rep = prior/poster .loc
        # TODO: loc will work, change to sample later
        if target_y is not None:
            # NOTICE: Training      *(context = test) for neural process
            post_dist, post_mu, post_sigma = self._latent_encoder(target_x, target_y)
            Z = post_dist.loc
        else:
            # NOTICE: Testing
            Z = prior_dist.loc
        # Z (b, latent_dim)

        # print('before unsequeeze, Z.size() =', Z.size())

        Z = Z.unsqueeze(1).repeat(1, target_size, 1)
        # Z (b, target_size, latent_dim) verified

        # print('after unsequeeze, Z.size() =', Z.size())

        # NOTICE: obtain r using deterministic path
        if self.use_deter_path:
            R = self._deter_encoder(context_x, context_y, target_x)
            # R (B, target_size, latent_dim)
        else:
            R = None

        # Obtain the prediction
        dist, mu, sigma = self._decoder(R, Z, target_x)

        # If we want to calculate the log_prob for training we will make use of the
        # target_y. At test time the target_y is not available so we return None.
        if target_y is not None:
            # get log probability
            # Get KL between prior and posterior
            kl = torch.distributions.kl_divergence(post_dist, prior_dist).mean(-1)

            log_p = dist.log_prob(target_y).mean(-1)
            # print('log_p.size() =', log_p.size())
            # log_p = dist.log_prob(target_y).mean(-1)
            loss_kl = kl[:, None].expand(log_p.shape)
            # print('torch.mean(loss_kl) =', torch.mean(loss_kl))
            loss = - (log_p - loss_kl).mean()
        else:
            log_p = None
            kl = None
            loss = None

        return mu, sigma, log_p, kl, loss
